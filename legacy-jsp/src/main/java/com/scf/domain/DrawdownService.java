package com.scf.domain;

import com.scf.repository.*;
import java.math.BigDecimal;
import java.util.*;

public class DrawdownService {
    public static final BigDecimal FACILITY = new BigDecimal("500000.00");
    private final InvoiceRepository invoices = new InvoiceRepository();
    private final RequestRepository requests = new RequestRepository();
    public List<Invoice> invoices(String ref,String status,String currency){return invoices.find(ref,status,currency);}
    public BigDecimal available(){return new BigDecimal("320000.00").subtract(requests.utilized().subtract(new BigDecimal("180000.00")));}
    public List<Map<String,Object>> requestList(){return requests.all();}
    public Map<String,Object> getRequest(String ref){return requests.byRef(ref);}
    public Map<String,Object> dashboard(){Map<String,Object> m=new LinkedHashMap<>();m.put("supplierId","SUP-10042");m.put("supplierName","Apex Industrial Components Ltd.");m.put("programStatus","ACTIVE");m.put("facilityLimit",FACILITY);m.put("utilizedAmount",new BigDecimal("180000.00").add(requests.utilized().subtract(new BigDecimal("180000.00"))));m.put("availableLimit",available());m.put("recentActivity",requests.all());return m;}
    public Map<String,String> validate(DrawdownDraft d){return RuleEngine.validate(d,invoices.byRefs(d.invoiceRefs),available());}
    public String submit(DrawdownDraft d){return submit(d,"maker-1");}
    public String submit(DrawdownDraft d,String actorId){Map<String,String> e=validate(d);if(!e.isEmpty())throw new ValidationException(e);return requests.create(d.submissionToken,d.currency,d.requestedAmount,RuleEngine.discountFee(d.requestedAmount,d.tenorDays),RuleEngine.processingFee(),RuleEngine.netPayout(d.requestedAmount,d.tenorDays),d.tenorDays,d.beneficiaryCode,d.invoiceRefs,d.attachments,actorId);}
    public Map<String,Object> amend(String ref,String currency,BigDecimal amount,Integer tenorDays,String beneficiaryCode,String actorId,String role){
        if(!"MAKER_1".equals(role)) throw new GovernanceException(403,"Only a Maker can amend a request");
        Map<String,Object> existing=requests.byRef(ref);
        if(existing==null) throw new GovernanceException(404,"Request not found");
        DrawdownDraft d=new DrawdownDraft();
        d.invoiceRefs=new ArrayList<>(requests.invoicesFor(ref));
        d.currency=currency!=null?currency:(String)existing.get("currency");
        d.requestedAmount=amount!=null?amount:(BigDecimal)existing.get("requestedAmount");
        d.tenorDays=tenorDays!=null?tenorDays:(Integer)existing.get("tenorDays");
        d.beneficiaryCode=beneficiaryCode!=null?beneficiaryCode:(String)existing.get("beneficiaryCode");
        d.termsAcknowledged=true;
        d.attachments=requests.attachmentsFor(ref);
        List<Invoice> selected=invoices.byRefs(d.invoiceRefs).stream()
                .map(i -> new Invoice(i.ref(),i.status(),i.currency(),i.amount(),BigDecimal.ZERO)).toList();
        BigDecimal self=(BigDecimal)existing.get("requestedAmount");
        Map<String,String> errors=RuleEngine.validate(d,selected,available().add(self==null?BigDecimal.ZERO:self));
        if(!errors.isEmpty()) throw new ValidationException(errors);
        requests.updateAmend(ref,d.currency,d.requestedAmount,RuleEngine.discountFee(d.requestedAmount,d.tenorDays),RuleEngine.processingFee(),RuleEngine.netPayout(d.requestedAmount,d.tenorDays),d.tenorDays,d.beneficiaryCode,actorId);
        return requests.byRef(ref);
    }
    public Map<String,Object> checkerAction(String ref,int level,String action,String reason,String actorId,String role){
        String required=level==1?"CHECKER_1":"CHECKER_2";
        if(!required.equals(role)) throw new GovernanceException(403,"Requires role "+required);
        Map<String,Object> existing=requests.byRef(ref);
        if(existing==null) throw new GovernanceException(404,"Request not found");
        String normalized=action==null?"":action.trim().toUpperCase();
        if(!"APPROVE".equals(normalized)&&!"REJECT".equals(normalized)) throw new GovernanceException(400,"Action must be APPROVE or REJECT");
        String created=(String)existing.get("createdBy"), amended=(String)existing.get("amendedBy");
        String stage=(String)existing.get("approvalStage");
        if(level==1){
            if(Objects.equals(actorId,created)||(amended!=null&&Objects.equals(actorId,amended))) throw new GovernanceException(400,"Maker cannot act as First Checker");
            if(!"PENDING_CHECKER_1".equals(stage)) throw new GovernanceException(400,"Request must be in PENDING_CHECKER_1 for First Checker action");
        }else{
            String first=(String)existing.get("checker1By");
            if(Objects.equals(actorId,created)||(amended!=null&&Objects.equals(actorId,amended))||(first!=null&&Objects.equals(actorId,first))) throw new GovernanceException(400,"Second Checker must be distinct from Maker and First Checker");
            if(!"PENDING_CHECKER_2".equals(stage)) throw new GovernanceException(400,"Request must be in PENDING_CHECKER_2 for Second Checker action");
        }
        String next;
        try{ next=RuleEngine.nextStage(stage,normalized); }catch(IllegalArgumentException e){ throw new GovernanceException(400,e.getMessage()); }
        requests.updateStage(ref,next,level,actorId,"REJECTED".equals(next)?reason:null);
        if("REJECTED".equals(next)) requests.releaseInvoices(ref);
        return requests.byRef(ref);
    }
    public static class ValidationException extends RuntimeException {public final Map<String,String> errors;public ValidationException(Map<String,String> e){super("Validation failed");errors=e;}}
    public static class GovernanceException extends RuntimeException {public final int status;public GovernanceException(int status,String message){super(message);this.status=status;}}
}
