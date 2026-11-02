package com.scf.domain;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

public final class AuthBridgeService {
    public static final long TTL_SECONDS = 1800L;
    public static final String MAKER_1 = "MAKER_1";
    public static final String CHECKER_1 = "CHECKER_1";
    public static final String CHECKER_2 = "CHECKER_2";
    private static final Map<String, String> DEFAULT_ROLES = Map.of(
            "maker-1", MAKER_1, "checker-1", CHECKER_1, "checker-2", CHECKER_2);
    private static final Set<String> VALID_ROLES = Set.of(MAKER_1, CHECKER_1, CHECKER_2);
    private static final AtomicLong EPOCH = new AtomicLong(0);

    public record Actor(String actorId, String role) {}
    public record Claims(String sessionId, String actorId, String role, long issuedAt, long expiresAt) {}
    record Minted(String token, long issuedAt, long expiresAt) {}

    private AuthBridgeService() {}

    static String secret() {
        String configured = System.getenv("PARITY_BRIDGE_SECRET");
        return (configured == null || configured.isBlank()) ? "northstar-parity-dev-secret-01" : configured;
    }

    public static void bumpEpoch() { EPOCH.incrementAndGet(); }

    public static String mint(String sessionId, String actorId, String role) {
        return mintDetailed(sessionId, actorId, role, TTL_SECONDS).token();
    }

    public static String mint(String sessionId, String actorId, String role, long ttlSeconds) {
        return mintDetailed(sessionId, actorId, role, ttlSeconds).token();
    }

    static Minted mintDetailed(String sessionId, String actorId, String role, long ttlSeconds) {
        long now = Instant.now().getEpochSecond();
        long expiresAt = now + ttlSeconds;
        String payload = "{\"sessionId\":\"" + esc(sessionId) + "\",\"actorId\":\"" + esc(actorId)
                + "\",\"role\":\"" + esc(role) + "\",\"issuedAt\":" + now
                + ",\"expiresAt\":" + expiresAt + ",\"epoch\":" + EPOCH.get() + "}";
        String body = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(payload.getBytes(StandardCharsets.UTF_8));
        String token = body + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(hmac(body));
        return new Minted(token, now, expiresAt);
    }

    public static Optional<Claims> validate(String token) {
        try {
            if (token == null) return Optional.empty();
            String[] parts = token.split("\\.");
            if (parts.length != 2) return Optional.empty();
            byte[] signature = Base64.getUrlDecoder().decode(parts[1]);
            if (!MessageDigest.isEqual(signature, hmac(parts[0]))) return Optional.empty();
            Map<String, String> fields = parse(new String(
                    Base64.getUrlDecoder().decode(parts[0]), StandardCharsets.UTF_8));
            long expiresAt = Long.parseLong(fields.get("expiresAt"));
            if (Instant.now().getEpochSecond() > expiresAt) return Optional.empty();
            if (Long.parseLong(fields.get("epoch")) != EPOCH.get()) return Optional.empty();
            return Optional.of(new Claims(fields.get("sessionId"), fields.get("actorId"),
                    fields.get("role"), Long.parseLong(fields.get("issuedAt")), expiresAt));
        } catch (RuntimeException e) {
            return Optional.empty();
        }
    }

    public static boolean isValidRole(String role) { return role != null && VALID_ROLES.contains(role); }

    public static String defaultRole(String actorId) {
        return DEFAULT_ROLES.getOrDefault(actorId == null ? "" : actorId, MAKER_1);
    }

    public static Actor resolveActor(HttpServletRequest req) {
        String authorization = req.getHeader("Authorization");
        if (authorization != null && authorization.startsWith("Bearer ")) {
            var claims = validate(authorization.substring(7).trim());
            if (claims.isPresent()) return new Actor(claims.get().actorId(), claims.get().role());
        }
        String actorId = firstNonBlank(req.getHeader("X-Actor-Id"), req.getParameter("actorId"),
                sessionAttr(req, "SCF_ACTOR_ID"), "maker-1");
        String role = firstValidRole(req.getHeader("X-Actor-Role"), req.getParameter("role"),
                sessionAttr(req, "SCF_ACTOR_ROLE"));
        return new Actor(actorId, role == null ? defaultRole(actorId) : role);
    }

    private static String sessionAttr(HttpServletRequest req, String key) {
        HttpSession session = req.getSession(false);
        if (session == null) return null;
        Object value = session.getAttribute(key);
        return value == null ? null : value.toString();
    }

    private static String firstNonBlank(String... values) {
        for (String v : values) if (v != null && !v.isBlank()) return v;
        return null;
    }

    private static String firstValidRole(String... values) {
        for (String v : values) if (isValidRole(v)) return v;
        return null;
    }

    private static byte[] hmac(String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret().getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            throw new IllegalStateException("HMAC unavailable", e);
        }
    }

    private static String esc(String value) {
        return value == null ? "" : value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    static Map<String, String> parse(String json) {
        Map<String, String> fields = new LinkedHashMap<>();
        String inner = json.trim();
        inner = inner.substring(1, inner.length() - 1);
        for (String part : inner.split(",")) {
            int sep = part.indexOf(':');
            if (sep < 0) throw new IllegalArgumentException("bad token payload");
            fields.put(unquote(part.substring(0, sep)), unquote(part.substring(sep + 1)));
        }
        return fields;
    }

    private static String unquote(String value) {
        String text = value.trim();
        if (text.length() >= 2 && text.startsWith("\"") && text.endsWith("\"")) {
            return text.substring(1, text.length() - 1).replace("\\\"", "\"").replace("\\\\", "\\");
        }
        return text;
    }
}
