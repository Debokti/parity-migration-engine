package com.scf;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.scf.config.AppContext;
import com.scf.config.CoexistenceHeaderFilter;
import com.scf.config.CorsFilter;
import com.scf.config.ParityDevServlet;
import com.scf.controller.api.ApiServlet;
import com.scf.domain.*;
import com.scf.repository.Database;
import javax.servlet.*;
import javax.servlet.http.*;
import org.junit.jupiter.api.Test;
import java.io.*;
import java.lang.reflect.Proxy;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class AuthBridgeAndGovernanceTest {
    static class Fake {
        final Map<String, Object> sessionAttrs = new HashMap<>();
        final Map<String, Object> requestAttrs = new HashMap<>();
        final Map<String, String[]> params = new HashMap<>();
        final Map<String, String> headers = new HashMap<>();
        final Map<String, String> responseHeaders = new LinkedHashMap<>();
        final StringWriter body = new StringWriter();
        String method = "GET";
        String pathInfo = null;
        String requestBody = "";
        int status = 200;
        int errorStatus = 0;
        String sessionId = "test-session-1";
        boolean invalidated = false;
        boolean chainCalled = false;
        final HttpSession session = (HttpSession) Proxy.newProxyInstance(Fake.class.getClassLoader(),
                new Class[]{HttpSession.class}, (proxy, m, a) -> switch (m.getName()) {
                    case "getId" -> sessionId;
                    case "getAttribute" -> sessionAttrs.get((String) a[0]);
                    case "setAttribute" -> {
                        sessionAttrs.put((String) a[0], a[1]);
                        yield null;
                    }
                    case "invalidate" -> {
                        invalidated = true;
                        yield null;
                    }
                    default -> null;
                });
    }

    private HttpServletRequest request(Fake f) {
        return (HttpServletRequest) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class[]{HttpServletRequest.class}, (proxy, m, a) -> switch (m.getName()) {
                    case "getMethod" -> f.method;
                    case "getPathInfo" -> f.pathInfo;
                    case "getHeader" -> f.headers.get((String) a[0]);
                    case "getParameter" -> {
                        String[] v = f.params.get((String) a[0]);
                        yield v == null ? null : v[0];
                    }
                    case "getParameterValues" -> f.params.get((String) a[0]);
                    case "getSession" -> f.session;
                    case "getContextPath" -> "";
                    case "getAttribute" -> f.requestAttrs.get((String) a[0]);
                    case "setAttribute" -> {
                        f.requestAttrs.put((String) a[0], a[1]);
                        yield null;
                    }
                    case "getInputStream" -> new ServletInputStream() {
                        private final ByteArrayInputStream in = new ByteArrayInputStream(
                                f.requestBody.getBytes(StandardCharsets.UTF_8));
                        public int read() throws IOException { return in.read(); }
                        public boolean isFinished() { return in.available() == 0; }
                        public boolean isReady() { return true; }
                        public void setReadListener(ReadListener l) {}
                    };
                    default -> null;
                });
    }

    private HttpServletResponse response(Fake f) {
        return (HttpServletResponse) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class[]{HttpServletResponse.class}, (proxy, m, a) -> {
                    switch (m.getName()) {
                        case "getWriter" -> { return new PrintWriter(f.body); }
                        case "setHeader" -> f.responseHeaders.put((String) a[0], (String) a[1]);
                        case "setStatus" -> f.status = (Integer) a[0];
                        case "sendError" -> f.errorStatus = (Integer) a[0];
                    }
                    return null;
                });
    }

    private FilterChain chain(Fake f) {
        return (FilterChain) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class[]{FilterChain.class}, (proxy, m, a) -> {
                    f.chainCalled = true;
                    return null;
                });
    }

    private final ObjectMapper json = new ObjectMapper();

    @SuppressWarnings("unchecked")
    private Map<String, Object> jsonBody(Fake f) throws Exception {
        return json.readValue(f.body.toString(), Map.class);
    }

    private DrawdownDraft draft(String token, String... refs) {
        DrawdownDraft d = new DrawdownDraft();
        d.invoiceRefs = new ArrayList<>(List.of(refs));
        d.currency = "USD";
        d.requestedAmount = new BigDecimal("5000");
        d.tenorDays = 30;
        d.beneficiaryCode = "BEN-US-001";
        d.termsAcknowledged = true;
        d.submissionToken = token;
        d.attachments = new ArrayList<>(List.of(new Attachment("INVOICE_COPY", "a.pdf", "application/pdf", 10)));
        return d;
    }

    @Test void tokenMintValidateRoundtrip() {
        String token = AuthBridgeService.mint("s1", "maker-1", "MAKER_1");
        var claims = AuthBridgeService.validate(token);
        assertTrue(claims.isPresent());
        assertEquals("s1", claims.get().sessionId());
        assertEquals("maker-1", claims.get().actorId());
        assertEquals("MAKER_1", claims.get().role());
        assertTrue(claims.get().expiresAt() > claims.get().issuedAt());
        assertEquals(AuthBridgeService.TTL_SECONDS, claims.get().expiresAt() - claims.get().issuedAt());
    }

    @Test void tokenTamperRejected() {
        String token = AuthBridgeService.mint("s1", "maker-1", "MAKER_1");
        String flipPayload = token.substring(0, 5) + (token.charAt(5) == 'A' ? 'B' : 'A') + token.substring(6);
        assertTrue(AuthBridgeService.validate(flipPayload).isEmpty());
        String flipSig = token.substring(0, token.length() - 1) + (token.endsWith("A") ? "B" : "A");
        assertTrue(AuthBridgeService.validate(flipSig).isEmpty());
    }

    @Test void tokenMalformedRejected() {
        assertTrue(AuthBridgeService.validate(null).isEmpty());
        assertTrue(AuthBridgeService.validate("").isEmpty());
        assertTrue(AuthBridgeService.validate("abc").isEmpty());
        assertTrue(AuthBridgeService.validate("a.b.c").isEmpty());
        assertTrue(AuthBridgeService.validate("a.!!!").isEmpty());
        assertTrue(AuthBridgeService.validate("!!!.!!!").isEmpty());
    }

    @Test void tokenExpiredRejected() {
        assertTrue(AuthBridgeService.validate(AuthBridgeService.mint("s1", "maker-1", "MAKER_1", -5)).isEmpty());
    }

    @Test void tokenEpochBumpRejects() {
        String before = AuthBridgeService.mint("s1", "maker-1", "MAKER_1");
        AuthBridgeService.bumpEpoch();
        assertTrue(AuthBridgeService.validate(before).isEmpty());
        assertTrue(AuthBridgeService.validate(AuthBridgeService.mint("s1", "maker-1", "MAKER_1")).isPresent());
    }

    @Test void tokenWeirdActorFailsClosed() {
        assertTrue(AuthBridgeService.validate(AuthBridgeService.mint(null, "a,b\"c", null)).isEmpty());
        String empty = AuthBridgeService.mint(null, null, null);
        var claims = AuthBridgeService.validate(empty);
        assertTrue(claims.isPresent());
        assertEquals("", claims.get().actorId());
    }

    @Test void resolveActorPrecedence() {
        Fake f = new Fake();
        assertEquals(new AuthBridgeService.Actor("maker-1", "MAKER_1"), AuthBridgeService.resolveActor(request(f)));
        f.params.put("actorId", new String[]{"checker-2"});
        assertEquals("checker-2", AuthBridgeService.resolveActor(request(f)).actorId());
        f.headers.put("X-Actor-Id", "checker-1");
        assertEquals("checker-1", AuthBridgeService.resolveActor(request(f)).actorId());
        f.sessionAttrs.put("SCF_ACTOR_ID", "maker-1");
        Fake g = new Fake();
        g.sessionAttrs.put("SCF_ACTOR_ID", "checker-1");
        assertEquals("checker-1", AuthBridgeService.resolveActor(request(g)).actorId());
    }

    @Test void resolveActorRoles() {
        Fake f = new Fake();
        f.headers.put("X-Actor-Id", "maker-1");
        f.headers.put("X-Actor-Role", "CHECKER_2");
        assertEquals("CHECKER_2", AuthBridgeService.resolveActor(request(f)).role());
        Fake g = new Fake();
        g.params.put("actorId", new String[]{"checker-2"});
        g.params.put("role", new String[]{"BOGUS"});
        assertEquals("CHECKER_2", AuthBridgeService.resolveActor(request(g)).role());
        Fake h = new Fake();
        h.sessionAttrs.put("SCF_ACTOR_ID", "checker-1");
        h.sessionAttrs.put("SCF_ACTOR_ROLE", "CHECKER_1");
        assertEquals("CHECKER_1", AuthBridgeService.resolveActor(request(h)).role());
        assertEquals("MAKER_1", AuthBridgeService.defaultRole("someone-new"));
        assertTrue(AuthBridgeService.isValidRole("MAKER_1"));
        assertFalse(AuthBridgeService.isValidRole("BOGUS"));
        assertFalse(AuthBridgeService.isValidRole(null));
    }

    @Test void resolveActorBearer() {
        String token = AuthBridgeService.mint("s9", "checker-1", "CHECKER_1");
        Fake f = new Fake();
        f.headers.put("Authorization", "Bearer " + token);
        f.headers.put("X-Actor-Id", "maker-1");
        assertEquals(new AuthBridgeService.Actor("checker-1", "CHECKER_1"),
                AuthBridgeService.resolveActor(request(f)));
        Fake g = new Fake();
        g.headers.put("Authorization", "Bearer garbage");
        g.headers.put("X-Actor-Id", "checker-2");
        assertEquals("checker-2", AuthBridgeService.resolveActor(request(g)).actorId());
        Fake h = new Fake();
        h.headers.put("Authorization", "Token abc");
        assertEquals("maker-1", AuthBridgeService.resolveActor(request(h)).actorId());
    }

    @Test void bridgeMintRoundtrip() throws Exception {
        DraftStore.clearAll();
        Fake f = new Fake();
        f.method = "GET"; f.pathInfo = "/auth/bridge"; f.sessionId = "bridge-s1";
        new ApiServlet().service(request(f), response(f));
        Map<String, Object> out = jsonBody(f);
        assertEquals("bridge-s1", out.get("sessionId"));
        assertEquals("maker-1", out.get("actorId"));
        assertEquals("MAKER_1", out.get("role"));
        assertTrue(AuthBridgeService.validate((String) out.get("token")).isPresent());
        assertEquals(out.get("token"), f.sessionAttrs.get("SCF_BEARER_TOKEN"));
        assertEquals("no-store, no-cache, must-revalidate", f.responseHeaders.get("Cache-Control"));
        assertEquals("no-cache", f.responseHeaders.get("Pragma"));
        assertEquals("0", f.responseHeaders.get("Expires"));
        Fake g = new Fake();
        g.method = "POST"; g.pathInfo = "/auth/token"; g.sessionId = "bridge-s2";
        g.headers.put("X-Actor-Id", "checker-1");
        new ApiServlet().service(request(g), response(g));
        assertEquals("checker-1", jsonBody(g).get("actorId"));
    }

    @Test void heartbeatValidatesAndRefreshes() throws Exception {
        String token = AuthBridgeService.mint("hb-s1", "checker-1", "CHECKER_1");
        Fake f = new Fake();
        f.method = "POST"; f.pathInfo = "/auth/heartbeat";
        f.headers.put("Authorization", "Bearer " + token);
        new ApiServlet().service(request(f), response(f));
        Map<String, Object> out = jsonBody(f);
        assertEquals(Boolean.TRUE, out.get("valid"));
        assertEquals("hb-s1", out.get("sessionId"));
        assertEquals("checker-1", out.get("actorId"));
        assertEquals("CHECKER_1", out.get("role"));
        assertTrue(((Number) out.get("remainingTtlSeconds")).longValue() > 0);
        Fake g = new Fake();
        g.method = "POST"; g.pathInfo = "/auth/heartbeat";
        new ApiServlet().service(request(g), response(g));
        assertEquals(401, g.status);
        assertEquals(Boolean.FALSE, jsonBody(g).get("valid"));
        Fake h = new Fake();
        h.method = "POST"; h.pathInfo = "/auth/heartbeat";
        h.headers.put("Authorization", "Bearer garbage");
        new ApiServlet().service(request(h), response(h));
        assertEquals(401, h.status);
        Fake i = new Fake();
        i.method = "POST"; i.pathInfo = "/auth/heartbeat";
        i.headers.put("Authorization", "Bearer " + AuthBridgeService.mint("x", "y", "MAKER_1", -5));
        new ApiServlet().service(request(i), response(i));
        assertEquals(401, i.status);
    }

    @Test void bearerDraftSyncAcrossSessionAndToken() throws Exception {
        DraftStore.clearAll();
        String token = AuthBridgeService.mint("sync-s1", "maker-1", "MAKER_1");
        Fake put = new Fake();
        put.method = "PUT"; put.pathInfo = "/draft"; put.sessionId = "other-session";
        put.headers.put("Authorization", "Bearer " + token);
        put.requestBody = "{\"invoiceRefs\":[\"INV-2026-101\"],\"currency\":\"USD\"}";
        new ApiServlet().service(request(put), response(put));
        Fake get = new Fake();
        get.method = "GET"; get.pathInfo = "/draft"; get.sessionId = "sync-s1";
        new ApiServlet().service(request(get), response(get));
        assertTrue(get.body.toString().contains("INV-2026-101"));
        Fake getBearer = new Fake();
        getBearer.method = "GET"; getBearer.pathInfo = "/draft"; getBearer.sessionId = "unrelated";
        getBearer.headers.put("Authorization", "Bearer " + token);
        new ApiServlet().service(request(getBearer), response(getBearer));
        assertTrue(getBearer.body.toString().contains("INV-2026-101"));
    }

    @Test void actorSwitchEndpoint() throws Exception {
        Fake f = new Fake();
        f.method = "POST"; f.pathInfo = "/actor";
        f.requestBody = "{\"actorId\":\"checker-2\"}";
        new ApiServlet().service(request(f), response(f));
        assertEquals("CHECKER_2", jsonBody(f).get("role"));
        assertEquals("checker-2", f.sessionAttrs.get("SCF_ACTOR_ID"));
        Fake g = new Fake();
        g.method = "POST"; g.pathInfo = "/actor";
        g.requestBody = "{\"actorId\":\"checker-1\",\"role\":\"MAKER_1\"}";
        new ApiServlet().service(request(g), response(g));
        assertEquals("MAKER_1", jsonBody(g).get("role"));
        Fake h = new Fake();
        h.method = "POST"; h.pathInfo = "/actor";
        h.requestBody = "{\"actorId\":\"\"}";
        new ApiServlet().service(request(h), response(h));
        assertEquals(400, h.status);
    }

    @Test void unknownApiPaths404() throws Exception {
        for (String method : new String[]{"GET", "POST", "PUT", "DELETE"}) {
            Fake f = new Fake();
            f.method = method; f.pathInfo = "/nope";
            new ApiServlet().service(request(f), response(f));
            assertEquals(404, f.errorStatus, method);
        }
        Fake g = new Fake();
        g.method = "GET"; g.pathInfo = null;
        new ApiServlet().service(request(g), response(g));
        assertTrue(g.body.toString().contains("SUP-10042"));
    }

    @Test void draftAttachmentsLifecycleBearer() throws Exception {
        DraftStore.clearAll();
        String token = AuthBridgeService.mint("att-s1", "maker-1", "MAKER_1");
        Fake post = new Fake();
        post.method = "POST"; post.pathInfo = "/draft/attachments"; post.sessionId = "att-s1";
        post.headers.put("Authorization", "Bearer " + token);
        post.requestBody = "{\"category\":\"INVOICE_COPY\",\"filename\":\"a.pdf\",\"fileType\":\"application/pdf\",\"sizeBytes\":5}";
        new ApiServlet().service(request(post), response(post));
        assertTrue(post.body.toString().contains("INVOICE_COPY"));
        Fake del = new Fake();
        del.method = "DELETE"; del.pathInfo = "/draft/attachments"; del.sessionId = "att-s1";
        del.headers.put("Authorization", "Bearer " + token);
        new ApiServlet().service(request(del), response(del));
        assertFalse(del.body.toString().contains("INVOICE_COPY"));
        new ApiServlet().service(request(del), response(del));
    }

    @Test void coexistenceHeadersSet() throws Exception {
        Fake f = new Fake();
        new CoexistenceHeaderFilter().doFilter(request(f), response(f), chain(f));
        assertEquals("no-store, no-cache, must-revalidate, max-age=0", f.responseHeaders.get("Cache-Control"));
        assertEquals("no-cache", f.responseHeaders.get("Pragma"));
        assertEquals("0", f.responseHeaders.get("Expires"));
        assertTrue(f.chainCalled);
    }

    @Test void corsFilterBehavior() throws Exception {
        Fake options = new Fake();
        options.method = "OPTIONS";
        new CorsFilter().doFilter(request(options), response(options), chain(options));
        assertEquals(204, options.status);
        assertFalse(options.chainCalled);
        Fake get = new Fake();
        get.method = "GET";
        new CorsFilter().doFilter(request(get), response(get), chain(get));
        assertEquals("http://localhost:4200", get.responseHeaders.get("Access-Control-Allow-Origin"));
        assertTrue(get.chainCalled);
    }

    @Test void parityResetAndState() throws Exception {
        Database.reset();
        DraftStore.clearAll();
        String before = AuthBridgeService.mint("rs-s1", "maker-1", "MAKER_1");
        Fake f = new Fake();
        f.method = "POST";
        new ParityDevServlet().service(request(f), response(f));
        assertTrue(f.body.toString().contains("\"reset\":true"));
        assertTrue(f.invalidated);
        assertTrue(AuthBridgeService.validate(before).isEmpty());
        assertTrue(AuthBridgeService.validate(AuthBridgeService.mint("rs-s1", "maker-1", "MAKER_1")).isPresent());
        Fake g = new Fake();
        g.method = "GET";
        new ParityDevServlet().service(request(g), response(g));
        assertTrue(g.body.toString().contains("recentActivity"));
    }

    @Test void parityDisabled404s() throws Exception {
        String previous = System.getProperty("parity.trace");
        System.setProperty("parity.trace", "false");
        try {
            Fake f = new Fake();
            f.method = "GET";
            new ParityDevServlet().service(request(f), response(f));
            assertEquals(404, f.errorStatus);
            Fake g = new Fake();
            g.method = "POST";
            new ParityDevServlet().service(request(g), response(g));
            assertEquals(404, g.errorStatus);
        } finally {
            if (previous == null) System.clearProperty("parity.trace");
            else System.setProperty("parity.trace", previous);
        }
    }

    @Test void draftStoreGuards() {
        DraftStore.clearAll();
        assertNull(DraftStore.get(null));
        DraftStore.save(null, new DrawdownDraft());
        DraftStore.save("x", null);
        DraftStore.clear(null);
        DraftStore.persist(null, new DrawdownDraft());
        assertNotNull(DraftStore.reconcile(null));
        DrawdownDraft stored = new DrawdownDraft();
        stored.currency = "EUR";
        DraftStore.save("ds-s1", stored);
        Fake f = new Fake();
        f.sessionId = "ds-s1";
        assertSame(stored, DraftStore.reconcile(f.session));
        assertSame(stored, DraftStore.load(f.session, "ds-s1"));
        Fake g = new Fake();
        g.sessionId = "ds-s2";
        DrawdownDraft viaSession = new DrawdownDraft();
        viaSession.currency = "USD";
        g.sessionAttrs.put("SCF_DRAFT_REQUEST", viaSession);
        assertSame(viaSession, DraftStore.reconcile(g.session));
        assertSame(viaSession, DraftStore.load(g.session, "ds-unknown"));
        Fake h = new Fake();
        h.sessionId = "ds-s3";
        assertNotNull(DraftStore.reconcile(h.session));
        DraftStore.clear("ds-s1");
        assertNull(DraftStore.get("ds-s1"));
    }

    @Test void initializeSeedsEmptyDatabase() throws Exception {
        try (var c = Database.connection(); var s = c.createStatement()) {
            s.execute("DROP ALL OBJECTS");
        }
        Database.initialize();
        assertFalse(AppContext.SERVICE.invoices(null, null, null).isEmpty());
        Database.initialize();
        assertFalse(AppContext.SERVICE.requestList().isEmpty());
    }

    @Test void invoicesFilterBranches() {
        Database.reset();
        assertFalse(AppContext.SERVICE.invoices("INV-2026-10", null, null).isEmpty());
        assertFalse(AppContext.SERVICE.invoices(null, "APPROVED", null).isEmpty());
        assertFalse(AppContext.SERVICE.invoices(null, null, "EUR").isEmpty());
        assertTrue(AppContext.SERVICE.invoices("ZZZ-NOPE", "APPROVED", "USD").isEmpty());
        assertFalse(AppContext.SERVICE.invoices(null, null, null).isEmpty());
    }

    @Test void governanceCreateApproveApprove() {
        Database.reset();
        String ref = AppContext.SERVICE.submit(draft("gov-t1", "INV-2026-101", "INV-2026-102"), "maker-1");
        Map<String, Object> created = AppContext.SERVICE.getRequest(ref);
        assertEquals("PENDING_CHECKER_1", created.get("approvalStage"));
        assertEquals("maker-1", created.get("createdBy"));
        Map<String, Object> afterC1 = AppContext.SERVICE.checkerAction(ref, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        assertEquals("PENDING_CHECKER_2", afterC1.get("approvalStage"));
        assertEquals("checker-1", afterC1.get("checker1By"));
        Map<String, Object> afterC2 = AppContext.SERVICE.checkerAction(ref, 2, "APPROVE", null, "checker-2", "CHECKER_2");
        assertEquals("APPROVED", afterC2.get("approvalStage"));
        assertEquals("checker-2", afterC2.get("checker2By"));
    }

    @Test void amendHappyPathAndReapproval() {
        Database.reset();
        String ref = AppContext.SERVICE.submit(draft("am-t1", "INV-2026-101", "INV-2026-102"), "maker-1");
        Map<String, Object> amended = AppContext.SERVICE.amend(ref, "USD", new BigDecimal("6000"), 60,
                "BEN-US-123", "maker-1", "MAKER_1");
        assertEquals(0, ((BigDecimal) amended.get("requestedAmount")).compareTo(new BigDecimal("6000")));
        assertEquals(60, amended.get("tenorDays"));
        assertEquals("BEN-US-123", amended.get("beneficiaryCode"));
        assertEquals("maker-1", amended.get("amendedBy"));
        assertEquals("PENDING_CHECKER_1", amended.get("approvalStage"));
        assertNull(amended.get("checker1By"));
        Map<String, Object> kept = AppContext.SERVICE.amend(ref, null, null, null, null, "maker-1", "MAKER_1");
        assertEquals(0, ((BigDecimal) kept.get("requestedAmount")).compareTo(new BigDecimal("6000")));
        Map<String, Object> tenorOnly = AppContext.SERVICE.amend(ref, null, null, 90, null, "maker-1", "MAKER_1");
        assertEquals(90, tenorOnly.get("tenorDays"));
        assertEquals(0, ((BigDecimal) tenorOnly.get("requestedAmount")).compareTo(new BigDecimal("6000")));
        Map<String, Object> afterC1 = AppContext.SERVICE.checkerAction(ref, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        assertEquals("PENDING_CHECKER_2", afterC1.get("approvalStage"));
    }

    @Test void amendInvalidAmountUnknownRefNonMaker() {
        Database.reset();
        String ref = AppContext.SERVICE.submit(draft("am-t2", "INV-2026-101"), "maker-1");
        assertThrows(DrawdownService.ValidationException.class, () ->
                AppContext.SERVICE.amend(ref, "USD", new BigDecimal("999999"), 30, "BEN-US-001", "maker-1", "MAKER_1"));
        var missing = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.amend("REQ-2026-9999", "USD", new BigDecimal("1000"), 30, "BEN-US-001", "maker-1", "MAKER_1"));
        assertEquals(404, missing.status);
        var forbidden = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.amend(ref, "USD", new BigDecimal("1000"), 30, "BEN-US-001", "checker-1", "CHECKER_1"));
        assertEquals(403, forbidden.status);
    }

    @Test void separationOfDuties() {
        Database.reset();
        String a = AppContext.SERVICE.submit(draft("sod-t1", "INV-2026-101"), "maker-1");
        var e1 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(a, 1, "APPROVE", null, "maker-1", "CHECKER_1"));
        assertEquals(400, e1.status);
        assertEquals("Maker cannot act as First Checker", e1.getMessage());
        AppContext.SERVICE.amend(a, "USD", new BigDecimal("6000"), 30, "BEN-US-001", "maker-2", "MAKER_1");
        var e2 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(a, 1, "APPROVE", null, "maker-2", "CHECKER_1"));
        assertEquals(400, e2.status);
        String b = AppContext.SERVICE.submit(draft("sod-t2", "INV-2026-102"), "maker-1");
        AppContext.SERVICE.checkerAction(b, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        var e3 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(b, 2, "APPROVE", null, "checker-1", "CHECKER_2"));
        assertEquals(400, e3.status);
        assertEquals("Second Checker must be distinct from Maker and First Checker", e3.getMessage());
        var e4 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(b, 2, "APPROVE", null, "maker-1", "CHECKER_2"));
        assertEquals(400, e4.status);
        AppContext.SERVICE.amend(b, "USD", new BigDecimal("6000"), 30, "BEN-US-001", "maker-2", "MAKER_1");
        AppContext.SERVICE.checkerAction(b, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        var e5 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(b, 2, "APPROVE", null, "maker-2", "CHECKER_2"));
        assertEquals(400, e5.status);
    }

    @Test void stageAndRoleGuards() {
        Database.reset();
        String c = AppContext.SERVICE.submit(draft("grd-t1", "INV-2026-101"), "maker-1");
        var early = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(c, 2, "APPROVE", null, "checker-2", "CHECKER_2"));
        assertEquals(400, early.status);
        var role1 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(c, 1, "APPROVE", null, "maker-1", "MAKER_1"));
        assertEquals(403, role1.status);
        var badAction = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(c, 1, "HOLD", null, "checker-1", "CHECKER_1"));
        assertEquals(400, badAction.status);
        var nullAction = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(c, 1, null, null, "checker-1", "CHECKER_1"));
        assertEquals(400, nullAction.status);
        AppContext.SERVICE.checkerAction(c, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        var twice = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(c, 1, "APPROVE", null, "checker-1", "CHECKER_1"));
        assertEquals(400, twice.status);
        String d = AppContext.SERVICE.submit(draft("grd-t2", "INV-2026-102"), "maker-1");
        var role2 = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction(d, 2, "APPROVE", null, "checker-1", "CHECKER_1"));
        assertEquals(403, role2.status);
        var missing = assertThrows(DrawdownService.GovernanceException.class, () ->
                AppContext.SERVICE.checkerAction("REQ-2026-9999", 1, "APPROVE", null, "checker-1", "CHECKER_1"));
        assertEquals(404, missing.status);
    }

    @Test void rejectionReleases() {
        Database.reset();
        String a = AppContext.SERVICE.submit(draft("rej-t1", "INV-2026-101"), "maker-1");
        Map<String, Object> rejected = AppContext.SERVICE.checkerAction(a, 1, "REJECT", "bad docs", "checker-1", "CHECKER_1");
        assertEquals("REJECTED", rejected.get("approvalStage"));
        assertEquals("bad docs", rejected.get("rejectionReason"));
        assertEquals("checker-1", rejected.get("checker1By"));
        Invoice released = AppContext.SERVICE.invoices("INV-2026-101", null, null).get(0);
        assertEquals(0, released.financedAmount().compareTo(BigDecimal.ZERO));
        assertEquals("ELIGIBLE", released.eligibility());
        String b = AppContext.SERVICE.submit(draft("rej-t2", "INV-2026-102"), "maker-1");
        AppContext.SERVICE.checkerAction(b, 1, "APPROVE", null, "checker-1", "CHECKER_1");
        Map<String, Object> rejected2 = AppContext.SERVICE.checkerAction(b, 2, "REJECT", "limit breach", "checker-2", "CHECKER_2");
        assertEquals("REJECTED", rejected2.get("approvalStage"));
        assertEquals("checker-2", rejected2.get("checker2By"));
        assertEquals(0, AppContext.SERVICE.invoices("INV-2026-102", null, null).get(0).financedAmount().compareTo(BigDecimal.ZERO));
    }

    @Test void idempotentSubmitKeepsStage() {
        Database.reset();
        // Validation runs before the submissionToken lookup, so the retry must reference a
        // still-eligible invoice (101 is financed by the first submit). Same token still
        // dedupes to the first request, mirroring the Scenario 4 token-reuse path.
        String first = AppContext.SERVICE.submit(draft("idem-t1", "INV-2026-101"), "maker-1");
        String second = AppContext.SERVICE.submit(draft("idem-t1", "INV-2026-102"), "maker-1");
        assertEquals(first, second);
        assertEquals("PENDING_CHECKER_1", AppContext.SERVICE.getRequest(first).get("approvalStage"));
        assertNull(AppContext.SERVICE.getRequest("REQ-2026-9999"));
    }

    @Test void apiGovernanceHappyPath() throws Exception {
        Database.reset();
        Fake submit = new Fake();
        submit.method = "POST"; submit.pathInfo = "/requests/submit";
        submit.headers.put("X-Actor-Id", "maker-1");
        submit.requestBody = json.writeValueAsString(draft("api-t1", "INV-2026-101", "INV-2026-102"));
        new ApiServlet().service(request(submit), response(submit));
        assertEquals(201, submit.status);
        Map<String, Object> created = jsonBody(submit);
        assertEquals("PENDING_CHECKER_1", created.get("approvalStage"));
        assertEquals("maker-1", created.get("createdBy"));
        String ref = (String) created.get("ref");
        Fake amend = new Fake();
        amend.method = "PUT"; amend.pathInfo = "/requests/" + ref + "/amend";
        amend.headers.put("X-Actor-Id", "maker-1");
        amend.requestBody = "{\"tenorDays\":60}";
        new ApiServlet().service(request(amend), response(amend));
        assertEquals("PENDING_CHECKER_1", jsonBody(amend).get("approvalStage"));
        Fake c1 = new Fake();
        c1.method = "POST"; c1.pathInfo = "/requests/" + ref + "/checker1";
        c1.headers.put("X-Actor-Id", "checker-1");
        c1.requestBody = "{\"action\":\"approve\"}";
        new ApiServlet().service(request(c1), response(c1));
        assertEquals("PENDING_CHECKER_2", jsonBody(c1).get("approvalStage"));
        Fake c2 = new Fake();
        c2.method = "POST"; c2.pathInfo = "/requests/" + ref + "/checker2";
        c2.headers.put("X-Actor-Id", "checker-2");
        c2.requestBody = "{\"action\":\"APPROVE\"}";
        new ApiServlet().service(request(c2), response(c2));
        assertEquals("APPROVED", jsonBody(c2).get("approvalStage"));
    }

    @Test void apiGovernanceErrors() throws Exception {
        Database.reset();
        Fake submit = new Fake();
        submit.method = "POST"; submit.pathInfo = "/requests/submit";
        submit.headers.put("X-Actor-Id", "maker-1");
        submit.requestBody = json.writeValueAsString(draft("api-t2", "INV-2026-101"));
        new ApiServlet().service(request(submit), response(submit));
        String ref = (String) jsonBody(submit).get("ref");
        Fake sod = new Fake();
        sod.method = "POST"; sod.pathInfo = "/requests/" + ref + "/checker1";
        sod.headers.put("X-Actor-Id", "maker-1");
        sod.headers.put("X-Actor-Role", "CHECKER_1");
        sod.requestBody = "{\"action\":\"APPROVE\"}";
        new ApiServlet().service(request(sod), response(sod));
        assertEquals(400, sod.status);
        assertEquals("Maker cannot act as First Checker", jsonBody(sod).get("error"));
        Fake role = new Fake();
        role.method = "POST"; role.pathInfo = "/requests/" + ref + "/checker1";
        role.headers.put("X-Actor-Id", "checker-2");
        role.requestBody = "{\"action\":\"APPROVE\"}";
        new ApiServlet().service(request(role), response(role));
        assertEquals(403, role.status);
        Fake missing = new Fake();
        missing.method = "POST"; missing.pathInfo = "/requests/REQ-2026-9999/checker1";
        missing.headers.put("X-Actor-Id", "checker-1");
        missing.requestBody = "{\"action\":\"APPROVE\"}";
        new ApiServlet().service(request(missing), response(missing));
        assertEquals(404, missing.status);
        Fake badAmount = new Fake();
        badAmount.method = "PUT"; badAmount.pathInfo = "/requests/" + ref + "/amend";
        badAmount.headers.put("X-Actor-Id", "maker-1");
        badAmount.requestBody = "{\"requestedAmount\":\"abc\"}";
        new ApiServlet().service(request(badAmount), response(badAmount));
        assertEquals(400, badAmount.status);
        Fake badTenor = new Fake();
        badTenor.method = "PUT"; badTenor.pathInfo = "/requests/" + ref + "/amend";
        badTenor.headers.put("X-Actor-Id", "maker-1");
        badTenor.requestBody = "{\"tenorDays\":\"x\"}";
        new ApiServlet().service(request(badTenor), response(badTenor));
        assertEquals(400, badTenor.status);
        Fake overCap = new Fake();
        overCap.method = "PUT"; overCap.pathInfo = "/requests/" + ref + "/amend";
        overCap.headers.put("X-Actor-Id", "maker-1");
        overCap.requestBody = "{\"requestedAmount\":999999}";
        new ApiServlet().service(request(overCap), response(overCap));
        assertEquals(400, overCap.status);
        assertTrue(overCap.body.toString().contains("requestedAmount"));
        Fake badSubmit = new Fake();
        badSubmit.method = "POST"; badSubmit.pathInfo = "/requests/submit";
        badSubmit.requestBody = "{}";
        new ApiServlet().service(request(badSubmit), response(badSubmit));
        assertEquals(400, badSubmit.status);
        Fake found = new Fake();
        found.method = "GET"; found.pathInfo = "/requests/" + ref;
        new ApiServlet().service(request(found), response(found));
        assertTrue(found.body.toString().contains(ref));
        Fake gone = new Fake();
        gone.method = "GET"; gone.pathInfo = "/requests/REQ-2026-9999";
        new ApiServlet().service(request(gone), response(gone));
        assertEquals("null", gone.body.toString());
    }
}
