package com.scf.repository;

import com.scf.domain.Attachment;
import java.math.BigDecimal;
import java.sql.*;
import java.util.*;

public class RequestRepository {
    private static final String COLUMNS = "ref,currency,requested_amount,discount_fee,processing_fee,net_payout,"
            + "tenor_days,beneficiary_code,created_at,created_by,approval_stage,amended_by,checker1_by,"
            + "checker2_by,rejection_reason";

    public String existingByToken(String token) {
        try (Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("SELECT ref FROM drawdown_requests WHERE submission_token=?")) {
            p.setString(1,token); try(ResultSet r=p.executeQuery()){return r.next()?r.getString(1):null;}
        } catch(SQLException e){throw new IllegalStateException("Unable to read requests",e);}
    }
    private Map<String,Object> row(ResultSet r)throws SQLException{
        Map<String,Object> m=new LinkedHashMap<>();
        m.put("ref",r.getString(1));m.put("currency",r.getString(2));m.put("requestedAmount",r.getBigDecimal(3));
        m.put("discountFee",r.getBigDecimal(4));m.put("processingFee",r.getBigDecimal(5));m.put("netPayout",r.getBigDecimal(6));
        m.put("tenorDays",r.getInt(7));m.put("beneficiaryCode",r.getString(8));m.put("createdAt",r.getTimestamp(9));
        m.put("createdBy",r.getString(10));m.put("approvalStage",r.getString(11));m.put("amendedBy",r.getString(12));
        m.put("checker1By",r.getString(13));m.put("checker2By",r.getString(14));m.put("rejectionReason",r.getString(15));
        return m;
    }
    public List<Map<String,Object>> all() {
        List<Map<String,Object>> out=new ArrayList<>();
        try(Connection c=Database.connection(); Statement s=c.createStatement(); ResultSet r=s.executeQuery("SELECT "+COLUMNS+" FROM drawdown_requests ORDER BY id")) {
            while(r.next()){out.add(row(r));} return out;
        } catch(SQLException e){throw new IllegalStateException("Unable to list requests",e);}
    }
    public Map<String,Object> byRef(String ref) {
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("SELECT "+COLUMNS+" FROM drawdown_requests WHERE ref=?")) {
            p.setString(1,ref); try(ResultSet r=p.executeQuery()){return r.next()?row(r):null;}
        } catch(SQLException e){throw new IllegalStateException("Unable to read request",e);}
    }
    public List<String> invoicesFor(String ref) {
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("SELECT invoice_ref FROM request_invoices WHERE request_ref=?")) {
            p.setString(1,ref); List<String> out=new ArrayList<>();
            try(ResultSet r=p.executeQuery()){while(r.next())out.add(r.getString(1));}
            return out;
        } catch(SQLException e){throw new IllegalStateException("Unable to read request invoices",e);}
    }
    public List<Attachment> attachmentsFor(String ref) {
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("SELECT category,filename,file_type,size_bytes FROM attachments WHERE request_ref=?")) {
            p.setString(1,ref); List<Attachment> out=new ArrayList<>();
            try(ResultSet r=p.executeQuery()){while(r.next())out.add(new Attachment(r.getString(1),r.getString(2),r.getString(3),r.getLong(4)));}
            return out;
        } catch(SQLException e){throw new IllegalStateException("Unable to read attachments",e);}
    }
    public BigDecimal utilized() { return all().stream().map(m -> (BigDecimal)m.get("requestedAmount")).reduce(BigDecimal.ZERO,BigDecimal::add); }
    public synchronized String create(String token,String currency,BigDecimal amount,BigDecimal discount,BigDecimal processing,BigDecimal net,int tenor,String beneficiary,List<String> invoices,List<Attachment> attachments,String createdBy) {
        String existing=existingByToken(token); if(existing!=null)return existing;
        String ref=String.format("REQ-2026-%04d",all().size()+1);
        try(Connection c=Database.connection()){c.setAutoCommit(false);
            try(PreparedStatement p=c.prepareStatement("INSERT INTO drawdown_requests(ref,submission_token,currency,requested_amount,discount_fee,processing_fee,net_payout,tenor_days,beneficiary_code,terms_acknowledged,created_at,created_by,approval_stage) VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?,'PENDING_CHECKER_1')")) {
                p.setString(1,ref);p.setString(2,token);p.setString(3,currency);p.setBigDecimal(4,amount);p.setBigDecimal(5,discount);p.setBigDecimal(6,processing);p.setBigDecimal(7,net);p.setInt(8,tenor);p.setString(9,beneficiary);p.setBoolean(10,true);p.setString(11,createdBy);p.executeUpdate();}
            try(PreparedStatement p=c.prepareStatement("INSERT INTO request_invoices VALUES(?,?)");PreparedStatement u=c.prepareStatement("UPDATE invoices SET financed_amount=amount WHERE ref=?")) {for(String i:invoices){p.setString(1,ref);p.setString(2,i);p.addBatch();u.setString(1,i);u.addBatch();}p.executeBatch();u.executeBatch();}
            if(attachments!=null&&!attachments.isEmpty()){
                try(PreparedStatement a=c.prepareStatement("INSERT INTO attachments(request_ref,category,filename,file_type,size_bytes) VALUES(?,?,?,?,?)")){
                    for(Attachment att:attachments){a.setString(1,ref);a.setString(2,att.category());a.setString(3,att.filename()!=null?att.filename():"");a.setString(4,att.fileType()!=null?att.fileType():"");a.setLong(5,att.sizeBytes());a.addBatch();}
                    a.executeBatch();
                }
            }
            c.commit();return ref;
        } catch(SQLException e){throw new IllegalStateException("Unable to create request",e);}
    }
    public synchronized void updateAmend(String ref,String currency,BigDecimal amount,BigDecimal discount,BigDecimal processing,BigDecimal net,int tenor,String beneficiary,String amendedBy) {
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("UPDATE drawdown_requests SET currency=?,requested_amount=?,discount_fee=?,processing_fee=?,net_payout=?,tenor_days=?,beneficiary_code=?,amended_by=?,approval_stage='PENDING_CHECKER_1',checker1_by=NULL,checker2_by=NULL,rejection_reason=NULL WHERE ref=?")) {
            p.setString(1,currency);p.setBigDecimal(2,amount);p.setBigDecimal(3,discount);p.setBigDecimal(4,processing);p.setBigDecimal(5,net);p.setInt(6,tenor);p.setString(7,beneficiary);p.setString(8,amendedBy);p.setString(9,ref);p.executeUpdate();
        } catch(SQLException e){throw new IllegalStateException("Unable to amend request",e);}
    }
    public synchronized void updateStage(String ref,String stage,int level,String checkerBy,String reason) {
        String column=level==1?"checker1_by":"checker2_by";
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("UPDATE drawdown_requests SET approval_stage=?,"+column+"=?,rejection_reason=? WHERE ref=?")) {
            p.setString(1,stage);p.setString(2,checkerBy);p.setString(3,reason);p.setString(4,ref);p.executeUpdate();
        } catch(SQLException e){throw new IllegalStateException("Unable to update stage",e);}
    }
    public synchronized void releaseInvoices(String ref) {
        try(Connection c=Database.connection(); PreparedStatement p=c.prepareStatement("UPDATE invoices SET financed_amount=0 WHERE ref IN (SELECT invoice_ref FROM request_invoices WHERE request_ref=?)")) {
            p.setString(1,ref);p.executeUpdate();
        } catch(SQLException e){throw new IllegalStateException("Unable to release invoices",e);}
    }
}
