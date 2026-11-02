package com.scf.domain;

import java.math.BigDecimal;

public record Invoice(String ref, String status, String currency, BigDecimal amount, BigDecimal financedAmount) {
    public String getRef() { return ref; }
    public String getStatus() { return status; }
    public BigDecimal getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public BigDecimal getFinancedAmount() { return financedAmount; }
    public String getEligibility() { return eligibility(); }
    public String eligibility() {
        if (!"APPROVED".equals(status)) return "NOT_APPROVED";
        if (financedAmount.signum() > 0) return "ALREADY_FINANCED";
        if (!currency.equals("USD") && !currency.equals("EUR")) return "UNSUPPORTED_CURRENCY";
        return "ELIGIBLE";
    }
}
