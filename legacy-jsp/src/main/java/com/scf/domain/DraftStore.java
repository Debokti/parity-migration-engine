package com.scf.domain;

import javax.servlet.http.HttpSession;
import java.util.concurrent.ConcurrentHashMap;

public final class DraftStore {
    private static final ConcurrentHashMap<String, DrawdownDraft> MAP = new ConcurrentHashMap<>();

    private DraftStore() {}

    public static DrawdownDraft get(String sessionId) {
        return sessionId == null ? null : MAP.get(sessionId);
    }

    public static void save(String sessionId, DrawdownDraft draft) {
        if (sessionId != null && draft != null) MAP.put(sessionId, draft);
    }

    public static void clear(String sessionId) {
        if (sessionId != null) MAP.remove(sessionId);
    }

    public static void clearAll() { MAP.clear(); }

    public static DrawdownDraft reconcile(HttpSession session) {
        if (session == null) return new DrawdownDraft();
        DrawdownDraft stored = get(session.getId());
        if (stored != null) return stored;
        Object attr = session.getAttribute("SCF_DRAFT_REQUEST");
        DrawdownDraft fresh = attr instanceof DrawdownDraft draft ? draft : new DrawdownDraft();
        save(session.getId(), fresh);
        return fresh;
    }

    public static void persist(HttpSession session, DrawdownDraft draft) {
        if (session == null || draft == null) return;
        session.setAttribute("SCF_DRAFT_REQUEST", draft);
        save(session.getId(), draft);
    }

    public static DrawdownDraft load(HttpSession session, String bearerSessionId) {
        DrawdownDraft viaBearer = get(bearerSessionId);
        return viaBearer != null ? viaBearer : reconcile(session);
    }
}
