package com.scf.config;

import javax.servlet.*;
import javax.servlet.http.*;
import java.io.IOException;

public class CoexistenceHeaderFilter implements Filter {
    public void doFilter(ServletRequest request,ServletResponse response,FilterChain chain)throws IOException,ServletException{
        HttpServletResponse r=(HttpServletResponse)response;
        r.setHeader("Cache-Control","no-store, no-cache, must-revalidate, max-age=0");
        r.setHeader("Pragma","no-cache");
        r.setHeader("Expires","0");
        chain.doFilter(request,response);
    }
}
