package com.scf.controller.api;

import com.fasterxml.jackson.databind.*;
import com.scf.config.AppContext;
import com.scf.domain.*;
import javax.servlet.http.*;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

public class ApiServlet extends HttpServlet {
    private final ObjectMapper json=new ObjectMapper();
    private AuthBridgeService.Claims bearer(HttpServletRequest req){
        String h=req.getHeader("Authorization");
        if(h!=null&&h.startsWith("Bearer ")){
            var claims=AuthBridgeService.validate(h.substring(7).trim());
            if(claims.isPresent()) return claims.get();
        }
        return null;
    }
    private DrawdownDraft loadDraft(HttpServletRequest req){
        var claims=bearer(req);
        return claims!=null?DraftStore.load(req.getSession(),claims.sessionId()):DraftStore.reconcile(req.getSession());
    }
    private void saveDraft(HttpServletRequest req,DrawdownDraft d){
        var claims=bearer(req);
        DraftStore.persist(req.getSession(),d);
        if(claims!=null) DraftStore.save(claims.sessionId(),d);
    }
    private String str(Object v){return v==null?null:v.toString().trim();}
    private BigDecimal decimal(Object v,String field){
        if(v==null) return null;
        try{return new BigDecimal(v.toString().trim());}
        catch(NumberFormatException e){throw new DrawdownService.GovernanceException(400,"Invalid "+field);}
    }
    private Integer integer(Object v,String field){
        if(v==null) return null;
        try{return Integer.valueOf(v.toString().trim());}
        catch(NumberFormatException e){throw new DrawdownService.GovernanceException(400,"Invalid "+field);}
    }
    private Map<String,Object> ok(String ref,Map<String,Object> row){
        Map<String,Object> m=new LinkedHashMap<>();
        m.put("ref",ref);m.put("status","SUBMITTED");
        m.put("approvalStage",row==null?null:row.get("approvalStage"));
        return m;
    }
    protected void doGet(HttpServletRequest req,HttpServletResponse res)throws IOException{
        String path=req.getPathInfo(); if(path==null||"/dashboard".equals(path)){write(res,AppContext.SERVICE.dashboard());return;}
        if("/invoices".equals(path)){write(res,AppContext.SERVICE.invoices(req.getParameter("ref"),req.getParameter("status"),req.getParameter("currency")));return;}
        if("/requests".equals(path)){write(res,AppContext.SERVICE.requestList());return;}
        if("/draft".equals(path)){write(res,loadDraft(req));return;}
        if("/auth/bridge".equals(path)){mintToken(req,res);return;}
        if(path.startsWith("/requests/")){String ref=path.substring("/requests/".length());write(res,AppContext.SERVICE.requestList().stream().filter(r -> ref.equals(r.get("ref"))).findFirst().orElse(null));return;}
        res.sendError(404);
    }
    protected void doPut(HttpServletRequest req,HttpServletResponse res)throws IOException{
        String path=req.getPathInfo();
        if("/draft".equals(path)){DrawdownDraft d=json.readValue(req.getInputStream(),DrawdownDraft.class);saveDraft(req,d);write(res,d);return;}
        if(path!=null&&path.startsWith("/requests/")&&path.endsWith("/amend")){
            String ref=path.substring("/requests/".length(),path.length()-"/amend".length());
            Map body=json.readValue(req.getInputStream(),Map.class);
            var actor=AuthBridgeService.resolveActor(req);
            try{
                Map<String,Object> row=AppContext.SERVICE.amend(ref,str(body.get("currency")),decimal(body.get("requestedAmount"),"requestedAmount"),integer(body.get("tenorDays"),"tenorDays"),str(body.get("beneficiaryCode")),actor.actorId(),actor.role());
                Map<String,Object> out=ok(ref,row);out.put("amendedBy",row.get("amendedBy"));write(res,out);
            }catch(DrawdownService.ValidationException e){res.setStatus(400);write(res,Map.of("errors",e.errors));}
            catch(DrawdownService.GovernanceException e){res.setStatus(e.status);write(res,Map.of("error",e.getMessage()));}
            return;
        }
        res.sendError(404);
    }
    protected void doPost(HttpServletRequest req,HttpServletResponse res)throws IOException{
        String path=req.getPathInfo();
        if("/auth/token".equals(path)){mintToken(req,res);return;}
        if("/auth/heartbeat".equals(path)){heartbeat(req,res);return;}
        if("/actor".equals(path)){switchActor(req,res);return;}
        if("/requests/submit".equals(path)){
            DrawdownDraft d=json.readValue(req.getInputStream(),DrawdownDraft.class);
            var actor=AuthBridgeService.resolveActor(req);
            try{String ref=AppContext.SERVICE.submit(d,actor.actorId());res.setStatus(201);Map<String,Object> out=ok(ref,AppContext.SERVICE.getRequest(ref));out.put("createdBy",actor.actorId());write(res,out);}
            catch(DrawdownService.ValidationException e){res.setStatus(400);write(res,Map.of("errors",e.errors));}
            return;
        }
        if(path!=null&&path.startsWith("/requests/")&&(path.endsWith("/checker1")||path.endsWith("/checker2"))){
            int level=path.endsWith("/checker1")?1:2;
            String ref=path.substring("/requests/".length(),path.lastIndexOf('/'));
            Map body=json.readValue(req.getInputStream(),Map.class);
            var actor=AuthBridgeService.resolveActor(req);
            Object reasonRaw=body.get("rejectionReason")!=null?body.get("rejectionReason"):body.get("reason");
            try{
                Map<String,Object> row=AppContext.SERVICE.checkerAction(ref,level,body.get("action")==null?null:body.get("action").toString(),reasonRaw==null?null:reasonRaw.toString(),actor.actorId(),actor.role());
                Map<String,Object> out=ok(ref,row);out.put(level==1?"checker1By":"checker2By",row.get(level==1?"checker1By":"checker2By"));write(res,out);
            }catch(DrawdownService.GovernanceException e){res.setStatus(e.status);write(res,Map.of("error",e.getMessage()));}
            return;
        }
        if("/draft/attachments".equals(path)){DrawdownDraft d=loadDraft(req);d.attachments.add(json.readValue(req.getInputStream(),Attachment.class));saveDraft(req,d);write(res,d);return;}
        res.sendError(404);
    }
    protected void doDelete(HttpServletRequest req,HttpServletResponse res)throws IOException{if("/draft/attachments".equals(req.getPathInfo())){DrawdownDraft d=loadDraft(req);if(!d.attachments.isEmpty())d.attachments.remove(d.attachments.size()-1);saveDraft(req,d);write(res,d);return;}res.sendError(404);}
    private void mintToken(HttpServletRequest req,HttpServletResponse res)throws IOException{
        res.setHeader("Cache-Control","no-store, no-cache, must-revalidate");
        res.setHeader("Pragma","no-cache");
        res.setHeader("Expires","0");
        HttpSession session=req.getSession();
        var actor=AuthBridgeService.resolveActor(req);
        String token=AuthBridgeService.mint(session.getId(),actor.actorId(),actor.role());
        session.setAttribute("SCF_BEARER_TOKEN",token);
        var claims=AuthBridgeService.validate(token).orElseThrow();
        Map<String,Object> out=new LinkedHashMap<>();
        out.put("token",token);out.put("sessionId",claims.sessionId());out.put("actorId",claims.actorId());
        out.put("role",claims.role());out.put("issuedAt",claims.issuedAt());out.put("expiresAt",claims.expiresAt());
        write(res,out);
    }
    private void heartbeat(HttpServletRequest req,HttpServletResponse res)throws IOException{
        var claims=bearer(req);
        if(claims==null){res.setStatus(401);write(res,Map.of("valid",false));return;}
        req.getSession();
        long ttl=Math.max(0,claims.expiresAt()-Instant.now().getEpochSecond());
        Map<String,Object> out=new LinkedHashMap<>();
        out.put("valid",true);out.put("sessionId",claims.sessionId());out.put("actorId",claims.actorId());
        out.put("role",claims.role());out.put("remainingTtlSeconds",ttl);
        write(res,out);
    }
    private void switchActor(HttpServletRequest req,HttpServletResponse res)throws IOException{
        Map body=json.readValue(req.getInputStream(),Map.class);
        String actorId=str(body.get("actorId"));
        if(actorId==null||actorId.isBlank()){res.setStatus(400);write(res,Map.of("error","actorId is required"));return;}
        String role=str(body.get("role"));
        if(!AuthBridgeService.isValidRole(role)) role=AuthBridgeService.defaultRole(actorId);
        req.getSession().setAttribute("SCF_ACTOR_ID",actorId);
        req.getSession().setAttribute("SCF_ACTOR_ROLE",role);
        write(res,Map.of("actorId",actorId,"role",role));
    }
    private void write(HttpServletResponse r,Object o)throws IOException{r.setContentType("application/json");json.writeValue(r.getWriter(),o);}
}
