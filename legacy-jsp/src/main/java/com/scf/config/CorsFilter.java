package com.scf.config;

import javax.servlet.*;
import javax.servlet.http.*;
import java.io.IOException;

public class CorsFilter implements Filter {
    static final String DEFAULT_ORIGIN = "http://localhost:4200";

    static String[] allowedOrigins() {
        String configured = System.getenv("CORS_ALLOWED_ORIGINS");
        if (configured == null || configured.isBlank()) return new String[]{DEFAULT_ORIGIN};
        return java.util.Arrays.stream(configured.split(",")).map(String::trim)
                .filter(s -> !s.isEmpty()).toArray(String[]::new);
    }

    static String selectOrigin(String requestOrigin) {
        String[] allowed = allowedOrigins();
        if (requestOrigin != null) for (String o : allowed) if (o.equals(requestOrigin)) return o;
        return allowed.length > 0 ? allowed[0] : DEFAULT_ORIGIN;
    }

    public void doFilter(ServletRequest request,ServletResponse response,FilterChain chain)throws IOException,ServletException{
        HttpServletResponse r=(HttpServletResponse)response;String origin=null;try{origin=((HttpServletRequest)request).getHeader("Origin");}catch(Exception ignored){}r.setHeader("Access-Control-Allow-Origin",selectOrigin(origin));r.setHeader("Access-Control-Allow-Methods","GET, POST, PUT, DELETE, OPTIONS");r.setHeader("Access-Control-Allow-Headers","*");r.setHeader("Access-Control-Allow-Credentials","true");if("OPTIONS".equalsIgnoreCase(((HttpServletRequest)request).getMethod())){r.setStatus(204);return;}chain.doFilter(request,response);
    }
}
