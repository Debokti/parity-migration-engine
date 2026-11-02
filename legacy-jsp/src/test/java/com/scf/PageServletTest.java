package com.scf;

import com.scf.controller.web.PageServlet;
import com.scf.domain.DrawdownDraft;
import com.scf.repository.Database;
import javax.servlet.*;
import javax.servlet.http.*;
import org.junit.jupiter.api.Test;
import java.lang.reflect.Proxy;
import java.math.BigDecimal;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PageServletTest {
    static class Fake {
        final Map<String, Object> sessionAttrs = new HashMap<>();
        final Map<String, Object> requestAttrs = new HashMap<>();
        final Map<String, String[]> params = new HashMap<>();
        String servletPath = "";
        String method = "POST";
        String redirect = "";
        String forwarded = "";
        int errorStatus = 0;
        final Map<String, String> headers = new HashMap<>();
        final HttpSession session = (HttpSession) Proxy.newProxyInstance(Fake.class.getClassLoader(), new Class[]{HttpSession.class},
                (proxy, m, a) -> switch (m.getName()) {
                    case "getAttribute" -> sessionAttrs.get((String) a[0]);
                    case "setAttribute" -> {
                        sessionAttrs.put((String) a[0], a[1]);
                        yield null;
                    }
                    default -> null;
                });
    }

    private HttpServletRequest request(Fake f) {
        return (HttpServletRequest) Proxy.newProxyInstance(getClass().getClassLoader(), new Class[]{HttpServletRequest.class},
                (proxy, m, a) -> switch (m.getName()) {
                    case "getMethod" -> f.method;
                    case "getServletPath" -> f.servletPath;
                    case "getHeader" -> f.headers.get((String) a[0]);
                    case "getParameter" -> {
                        String[] v = f.params.get((String) a[0]);
                        yield v == null ? null : v[0];
                    }
                    case "getParameterValues" -> f.params.get((String) a[0]);
                    case "getSession" -> f.session;
                    case "getContextPath" -> "";
                    case "setAttribute" -> {
                        f.requestAttrs.put((String) a[0], a[1]);
                        yield null;
                    }
                    case "getAttribute" -> f.requestAttrs.get((String) a[0]);
                    case "getRequestDispatcher" -> {
                        f.forwarded = (String) a[0];
                        yield (RequestDispatcher) Proxy.newProxyInstance(getClass().getClassLoader(),
                                new Class[]{RequestDispatcher.class}, (p2, m2, a2) -> null);
                    }
                    default -> null;
                });
    }

    private HttpServletResponse response(Fake f) {
        return (HttpServletResponse) Proxy.newProxyInstance(getClass().getClassLoader(), new Class[]{HttpServletResponse.class},
                (proxy, m, a) -> {
                    if ("sendRedirect".equals(m.getName())) f.redirect = (String) a[0];
                    if ("sendError".equals(m.getName())) f.errorStatus = (Integer) a[0];
                    return null;
                });
    }

    @Test void reviewPostBindsDrawdownParams() throws Exception {
        Fake f = new Fake();
        f.servletPath = "/review";
        f.params.put("requestedAmount", new String[]{"1000"});
        f.params.put("currency", new String[]{"USD"});
        f.params.put("tenorDays", new String[]{"30"});
        f.params.put("beneficiaryCode", new String[]{"BEN-US-123"});
        new PageServlet().service(request(f), response(f));
        DrawdownDraft d = (DrawdownDraft) f.sessionAttrs.get("SCF_DRAFT_REQUEST");
        assertEquals(new BigDecimal("1000"), d.requestedAmount);
        assertEquals("USD", d.currency);
        assertEquals(30, d.tenorDays);
        assertEquals("BEN-US-123", d.beneficiaryCode);
        assertTrue(f.redirect.endsWith("/attachments"));
    }

    @Test void attachmentsPostAddsAttachment() throws Exception {
        Fake f = new Fake();
        f.servletPath = "/attachments";
        f.params.put("category", new String[]{"INVOICE_COPY"});
        f.params.put("filename", new String[]{"a.pdf"});
        f.params.put("fileType", new String[]{"application/pdf"});
        f.params.put("sizeBytes", new String[]{"10"});
        new PageServlet().service(request(f), response(f));
        DrawdownDraft d = (DrawdownDraft) f.sessionAttrs.get("SCF_DRAFT_REQUEST");
        assertEquals(1, d.attachments.size());
        assertEquals("INVOICE_COPY", d.attachments.get(0).category());
        assertTrue(f.redirect.endsWith("/review"));
    }

    @Test void reviewSubmitReadsTermsAndToken() throws Exception {
        Database.initialize();
        Fake f = new Fake();
        f.servletPath = "/review/submit";
        f.params.put("termsAcknowledged", new String[]{"on"});
        new PageServlet().service(request(f), response(f));
        DrawdownDraft d = (DrawdownDraft) f.sessionAttrs.get("SCF_DRAFT_REQUEST");
        assertTrue(d.termsAcknowledged);
        assertNotNull(d.submissionToken);
        assertFalse(d.submissionToken.isBlank());
        assertEquals(d.submissionToken, f.sessionAttrs.get("submissionToken"));
        assertTrue(f.forwarded.endsWith("review.jsp"));
    }

    @Test void dashboardGetSetsActorAttributes() throws Exception {
        Database.reset();
        Fake f = new Fake(); f.method = "GET"; f.servletPath = "/dashboard";
        new PageServlet().service(request(f), response(f));
        assertTrue(f.forwarded.endsWith("dashboard.jsp"));
        assertEquals("maker-1", f.requestAttrs.get("actorId"));
        assertEquals("MAKER_1", f.requestAttrs.get("actorRole"));
    }

    @Test void invoicesGetForwardsWithFilters() throws Exception {
        Database.reset();
        Fake f = new Fake(); f.method = "GET"; f.servletPath = "/invoices";
        f.params.put("ref", new String[]{"INV-2026-10"});
        f.params.put("status", new String[]{"APPROVED"});
        f.params.put("currency", new String[]{"USD"});
        new PageServlet().service(request(f), response(f));
        assertTrue(f.forwarded.endsWith("invoices.jsp"));
        assertFalse(((List<?>) f.requestAttrs.get("invoices")).isEmpty());
    }

    @Test void staticPagesForwardAndUnknown404s() throws Exception {
        Database.reset();
        for (String path : new String[]{"/drawdown", "/attachments", "/requests"}) {
            Fake f = new Fake(); f.method = "GET"; f.servletPath = path;
            new PageServlet().service(request(f), response(f));
            assertTrue(f.forwarded.endsWith(".jsp"), path);
        }
        Fake f = new Fake(); f.method = "GET"; f.servletPath = "/nope";
        new PageServlet().service(request(f), response(f));
        assertEquals(404, f.errorStatus);
    }

    @Test void reviewGetEnsuresToken() throws Exception {
        Fake f = new Fake(); f.method = "GET"; f.servletPath = "/review";
        new PageServlet().service(request(f), response(f));
        assertTrue(f.forwarded.endsWith("review.jsp"));
        String token = (String) f.sessionAttrs.get("submissionToken");
        assertNotNull(token); assertFalse(token.isBlank());
        DrawdownDraft d = new DrawdownDraft(); d.submissionToken = "fixed-token";
        f.sessionAttrs.put("SCF_DRAFT_REQUEST", d);
        new PageServlet().service(request(f), response(f));
        assertEquals("fixed-token", f.sessionAttrs.get("submissionToken"));
    }

    @Test void actorSwitchSetsSessionAndRedirects() throws Exception {
        Fake f = new Fake(); f.servletPath = "/actor/switch";
        f.params.put("actorId", new String[]{"checker-1"});
        f.headers.put("Referer", "http://localhost:8080/dashboard");
        new PageServlet().service(request(f), response(f));
        assertEquals("checker-1", f.sessionAttrs.get("SCF_ACTOR_ID"));
        assertEquals("CHECKER_1", f.sessionAttrs.get("SCF_ACTOR_ROLE"));
        assertEquals("http://localhost:8080/dashboard", f.redirect);
        Fake g = new Fake(); g.servletPath = "/actor/switch";
        g.params.put("actorId", new String[]{"checker-2"}); g.params.put("role", new String[]{"MAKER_1"});
        new PageServlet().service(request(g), response(g));
        assertEquals("MAKER_1", g.sessionAttrs.get("SCF_ACTOR_ROLE"));
        assertTrue(g.redirect.endsWith("/dashboard"));
    }

    @Test void actorSwitchBlankActor400s() throws Exception {
        Fake f = new Fake(); f.servletPath = "/actor/switch";
        new PageServlet().service(request(f), response(f));
        assertEquals(400, f.errorStatus);
    }

    @Test void bindDrawdownInvalidNumbers() throws Exception {
        Fake f = new Fake(); f.servletPath = "/review";
        f.params.put("requestedAmount", new String[]{"abc"}); f.params.put("tenorDays", new String[]{"x"});
        new PageServlet().service(request(f), response(f));
        DrawdownDraft d = (DrawdownDraft) f.sessionAttrs.get("SCF_DRAFT_REQUEST");
        assertNull(d.requestedAmount); assertNull(d.tenorDays);
        Fake g = new Fake(); g.servletPath = "/attachments";
        g.params.put("category", new String[]{""});
        new PageServlet().service(request(g), response(g));
        assertTrue(((DrawdownDraft) g.sessionAttrs.get("SCF_DRAFT_REQUEST")).attachments.isEmpty());
        Fake h = new Fake(); h.servletPath = "/attachments";
        h.params.put("category", new String[]{"INVOICE_COPY"}); h.params.put("sizeBytes", new String[]{"junk"});
        new PageServlet().service(request(h), response(h));
        assertEquals(0L, ((DrawdownDraft) h.sessionAttrs.get("SCF_DRAFT_REQUEST")).attachments.get(0).sizeBytes());
    }

    @Test void confirmUploadLocksAndBlocksSameUserDeleteUntilAckOrNack() throws Exception {
        Database.reset();
        Fake f = new Fake();
        f.servletPath = "/attachments";
        f.params.put("action", new String[]{"confirmUpload"});
        f.params.put("stagedCategory", new String[]{"INVOICE_COPY", "PURCHASE_ORDER"});
        f.params.put("stagedFilename", new String[]{"inv1.pdf", "po1.pdf"});
        f.params.put("stagedFileType", new String[]{"application/pdf", "application/pdf"});
        f.params.put("stagedSizeBytes", new String[]{"1200", "2400"});
        new PageServlet().service(request(f), response(f));
        DrawdownDraft d = (DrawdownDraft) f.sessionAttrs.get("SCF_DRAFT_REQUEST");
        assertEquals(2, d.attachments.size());
        assertEquals("maker-1", f.sessionAttrs.get("SCF_UPLOAD_CONFIRMED_BY"));

        // Clear seeded APPROVED request so maker-1 has no completed ACK/NACK request
        try (var c = Database.connection(); var s = c.createStatement()) {
            s.execute("UPDATE drawdown_requests SET approval_stage='PENDING_CHECKER_1'");
        }
        f.params.clear();
        f.params.put("action", new String[]{"deleteConfirmed"});
        f.params.put("index", new String[]{"0"});
        new PageServlet().service(request(f), response(f));
        assertEquals(2, d.attachments.size());
        assertNotNull(f.sessionAttrs.get("SCF_UPLOAD_LOCK_ERROR"));

        // Once Maker-Checker reaches APPROVED (ACK), deletion and revert succeed
        Database.reset();
        new PageServlet().service(request(f), response(f));
        assertEquals(1, d.attachments.size());
        assertNull(f.sessionAttrs.get("SCF_UPLOAD_LOCK_ERROR"));

        f.params.put("action", new String[]{"revertConfirmed"});
        new PageServlet().service(request(f), response(f));
        assertTrue(d.attachments.isEmpty());
    }
}
