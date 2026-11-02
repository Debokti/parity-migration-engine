package com.scf.controller.web;

import com.scf.config.AppContext;
import com.scf.domain.*;
import javax.servlet.*;
import javax.servlet.http.*;
import java.io.IOException;

public class PageServlet extends HttpServlet {
    protected void doGet(HttpServletRequest req,HttpServletResponse res)throws ServletException,IOException{
        String path=req.getServletPath();if("/".equals(path)||"/dashboard".equals(path)){actorAttributes(req);req.setAttribute("dashboard",AppContext.SERVICE.dashboard());forward(req,res,"dashboard.jsp");}
        else if("/invoices".equals(path)){actorAttributes(req);req.setAttribute("invoices",AppContext.SERVICE.invoices(req.getParameter("ref"),req.getParameter("status"),req.getParameter("currency")));forward(req,res,"invoices.jsp");}
        else if("/drawdown".equals(path)){forward(req,res,"drawdown.jsp");} else if("/attachments".equals(path)){forward(req,res,"attachments.jsp");} else if("/review".equals(path)){ensureToken(req,draft(req));forward(req,res,"review.jsp");} else if("/requests".equals(path)){req.setAttribute("requests",AppContext.SERVICE.requestList());forward(req,res,"requests.jsp");} else res.sendError(404);
    }
    protected void doPost(HttpServletRequest req,HttpServletResponse res)throws ServletException,IOException{
        if("/invoices/select".equals(req.getServletPath())){DrawdownDraft d=draft(req);String[] refs=req.getParameterValues("invoiceRefs");d.invoiceRefs=refs==null?new java.util.ArrayList<>():new java.util.ArrayList<>(java.util.Arrays.asList(refs));DraftStore.persist(req.getSession(),d);res.sendRedirect(req.getContextPath()+"/drawdown");}
        else if("/actor/switch".equals(req.getServletPath())){switchActor(req,res);}
        else if("/review".equals(req.getServletPath())){bindDrawdown(req);res.sendRedirect(req.getContextPath()+"/attachments");}
        else if("/attachments".equals(req.getServletPath())){handleAttachmentsPost(req,res);}
        else if("/review/submit".equals(req.getServletPath())){DrawdownDraft d=draft(req);d.termsAcknowledged=req.getParameter("termsAcknowledged")!=null;ensureToken(req,d);DraftStore.persist(req.getSession(),d);try{String ref=AppContext.SERVICE.submit(d,AuthBridgeService.resolveActor(req).actorId());req.setAttribute("confirmation",ref);req.setAttribute("requests",AppContext.SERVICE.requestList());forward(req,res,"requests.jsp");}catch(DrawdownService.ValidationException e){req.setAttribute("errors",e.errors);forward(req,res,"review.jsp");}}
        else doGet(req,res);
    }
    private void actorAttributes(HttpServletRequest req){AuthBridgeService.Actor actor=AuthBridgeService.resolveActor(req);req.setAttribute("actorId",actor.actorId());req.setAttribute("actorRole",actor.role());}
    private void switchActor(HttpServletRequest req,HttpServletResponse res)throws IOException{
        String actorId=req.getParameter("actorId");
        if(actorId==null||actorId.isBlank()){res.sendError(400);return;}
        String role=req.getParameter("role");
        if(!AuthBridgeService.isValidRole(role)) role=AuthBridgeService.defaultRole(actorId.trim());
        req.getSession().setAttribute("SCF_ACTOR_ID",actorId.trim());
        req.getSession().setAttribute("SCF_ACTOR_ROLE",role);
        String back=req.getHeader("Referer");
        res.sendRedirect(back!=null&&!back.isBlank()?back:req.getContextPath()+"/dashboard");
    }
    private DrawdownDraft draft(HttpServletRequest r){return DraftStore.reconcile(r.getSession());}
    private void bindDrawdown(HttpServletRequest r){DrawdownDraft d=draft(r);d.requestedAmount=decimal(r.getParameter("requestedAmount"));d.currency=r.getParameter("currency");d.tenorDays=integer(r.getParameter("tenorDays"));d.beneficiaryCode=r.getParameter("beneficiaryCode");DraftStore.persist(r.getSession(),d);}
    private void bindAttachment(HttpServletRequest r){DrawdownDraft d=draft(r);String category=r.getParameter("category");if(category!=null&&!category.isBlank()){d.attachments.add(new Attachment(category,r.getParameter("filename"),r.getParameter("fileType"),longNum(r.getParameter("sizeBytes"))));}DraftStore.persist(r.getSession(),d);}
    private void handleAttachmentsPost(HttpServletRequest req,HttpServletResponse res)throws IOException{
        String action=req.getParameter("action");
        HttpSession session=req.getSession();
        String actorId=AuthBridgeService.resolveActor(req).actorId();
        if("confirmUpload".equals(action)){
            DrawdownDraft d=draft(req);
            String[] cats=req.getParameterValues("stagedCategory"),fns=req.getParameterValues("stagedFilename"),fts=req.getParameterValues("stagedFileType"),szs=req.getParameterValues("stagedSizeBytes");
            if(fns!=null){for(int i=0;i<fns.length;i++){if(fns[i]!=null&&!fns[i].isBlank())d.attachments.add(new Attachment(cats!=null&&i<cats.length?cats[i]:"INVOICE_COPY",fns[i],fts!=null&&i<fts.length?fts[i]:"application/octet-stream",longNum(szs!=null&&i<szs.length?szs[i]:"0")));}}
            DraftStore.persist(session,d);
            session.setAttribute("SCF_UPLOAD_CONFIRMED_BY",actorId);
            session.setAttribute("SCF_UPLOAD_LOCK_ERROR",null);
            res.sendRedirect(req.getContextPath()+"/attachments");
        }else if("deleteConfirmed".equals(action)||"revertConfirmed".equals(action)){
            String lockedBy=(String)session.getAttribute("SCF_UPLOAD_CONFIRMED_BY");
            boolean ackOrNack=AppContext.SERVICE.requestList().stream().anyMatch(r->actorId.equals(r.get("createdBy"))&&("APPROVED".equals(r.get("approvalStage"))||"REJECTED".equals(r.get("approvalStage"))));
            if(lockedBy!=null&&lockedBy.equals(actorId)&&!ackOrNack){
                session.setAttribute("SCF_UPLOAD_LOCK_ERROR","Files uploaded cannot be removed or reverted by the same user until ACK (APPROVED) or NACK (REJECTED) and Maker-Checker flow completes.");
            }else{
                DrawdownDraft d=draft(req);
                Integer idx=integer(req.getParameter("index"));
                if("revertConfirmed".equals(action)) d.attachments.clear();
                else if(idx!=null&&idx>=0&&idx<d.attachments.size()) d.attachments.remove((int)idx);
                DraftStore.persist(session,d);
                session.setAttribute("SCF_UPLOAD_LOCK_ERROR",null);
            }
            res.sendRedirect(req.getContextPath()+"/attachments");
        }else{
            bindAttachment(req);
            res.sendRedirect(req.getContextPath()+"/review");
        }
    }
    private void ensureToken(HttpServletRequest r,DrawdownDraft d){if(d.submissionToken==null||d.submissionToken.isBlank()){d.submissionToken=java.util.UUID.randomUUID().toString();}r.getSession().setAttribute("submissionToken",d.submissionToken);}
    private java.math.BigDecimal decimal(String v){try{return v==null||v.isBlank()?null:new java.math.BigDecimal(v.replace(",","").trim());}catch(NumberFormatException e){return null;}}
    private Integer integer(String v){try{return v==null||v.isBlank()?null:Integer.valueOf(v.trim());}catch(NumberFormatException e){return null;}}
    private long longNum(String v){try{return v==null||v.isBlank()?0L:Long.parseLong(v.replace(",","").trim());}catch(NumberFormatException e){return 0L;}}
    private void forward(HttpServletRequest r,HttpServletResponse s,String view)throws ServletException,IOException{r.getRequestDispatcher("/WEB-INF/views/"+view).forward(r,s);}
}
