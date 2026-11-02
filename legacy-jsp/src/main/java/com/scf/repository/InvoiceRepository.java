package com.scf.repository;

import com.scf.domain.Invoice;
import java.sql.*;
import java.util.*;

public class InvoiceRepository {
    public List<Invoice> find(String ref, String status, String currency) {
        StringBuilder q = new StringBuilder("SELECT ref,status,currency,amount,financed_amount FROM invoices WHERE 1=1");
        List<String> args = new ArrayList<>();
        if (ref != null && !ref.isBlank()) { q.append(" AND ref LIKE ?"); args.add("%" + ref + "%"); }
        if (status != null && !status.isBlank()) { q.append(" AND status=?"); args.add(status); }
        if (currency != null && !currency.isBlank()) { q.append(" AND currency=?"); args.add(currency); }
        List<Invoice> result = new ArrayList<>();
        try (Connection c = Database.connection(); PreparedStatement p = c.prepareStatement(q.toString())) {
            for (int i=0;i<args.size();i++) p.setString(i+1,args.get(i));
            try (ResultSet r=p.executeQuery()) { while(r.next()) result.add(new Invoice(r.getString(1),r.getString(2),r.getString(3),r.getBigDecimal(4),r.getBigDecimal(5))); }
            return result;
        } catch(SQLException e) { throw new IllegalStateException("Unable to read invoices", e); }
    }
    public List<Invoice> byRefs(List<String> refs) { return find(null,null,null).stream().filter(i -> refs.contains(i.ref())).toList(); }
}
