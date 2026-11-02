package com.scf.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.regex.Pattern;

public final class RuleEngine {
    private static final BigDecimal ADVANCE = new BigDecimal("0.85");
    private static final BigDecimal RATE = new BigDecimal("0.06");
    private static final Pattern BENEFICIARY = Pattern.compile("^BEN-[A-Z]{2}-[0-9]{3}$");

    public static BigDecimal maxAdvanceable(List<Invoice> invoices) {
        return invoices.stream().map(Invoice::amount).reduce(BigDecimal.ZERO, BigDecimal::add)
                .multiply(ADVANCE).setScale(2, RoundingMode.HALF_UP);
    }

    public static Map<String, String> validate(DrawdownDraft draft, List<Invoice> invoices, BigDecimal available) {
        Map<String, String> errors = new LinkedHashMap<>();
        if (draft.invoiceRefs == null || draft.invoiceRefs.isEmpty()) errors.put("invoiceRefs", "Select at least one invoice");
        List<Invoice> selected = invoices;
        if (selected.stream().anyMatch(i -> !"ELIGIBLE".equals(i.eligibility()))) errors.put("invoiceRefs", "One or more invoices are not eligible");
        if (draft.currency == null || (!"USD".equals(draft.currency) && !"EUR".equals(draft.currency))) errors.put("currency", "Currency must be USD or EUR");
        if (!selected.isEmpty() && draft.currency != null && selected.stream().anyMatch(i -> !draft.currency.equals(i.currency())))
            errors.put("currency", "Selected invoices must match request currency");
        BigDecimal max = maxAdvanceable(selected);
        if (draft.requestedAmount == null || draft.requestedAmount.compareTo(new BigDecimal("1000")) < 0 || draft.requestedAmount.compareTo(max) > 0)
            errors.put("requestedAmount", "Amount must be between 1,000.00 and " + max);
        if (draft.requestedAmount != null && draft.requestedAmount.compareTo(available) > 0) errors.put("requestedAmount", "Amount exceeds available program limit");
        if (draft.tenorDays == null || !Set.of(30, 60, 90).contains(draft.tenorDays)) errors.put("tenorDays", "Tenor must be 30, 60, or 90 days");
        if (draft.beneficiaryCode == null || !BENEFICIARY.matcher(draft.beneficiaryCode).matches()) errors.put("beneficiaryCode", "Enter a valid beneficiary code");
        if (!draft.termsAcknowledged) errors.put("termsAcknowledged", "Terms must be acknowledged");
        if (draft.attachments == null || draft.attachments.stream().noneMatch(a -> "INVOICE_COPY".equals(a.category())))
            errors.put("attachments", "At least one INVOICE_COPY attachment is required");
        return errors;
    }

    public static String nextStage(String stage, String action) {
        boolean approve = "APPROVE".equals(action);
        boolean reject = "REJECT".equals(action);
        if (!approve && !reject) throw new IllegalArgumentException("Action must be APPROVE or REJECT");
        if ("PENDING_CHECKER_1".equals(stage)) return approve ? "PENDING_CHECKER_2" : "REJECTED";
        if ("PENDING_CHECKER_2".equals(stage)) return approve ? "APPROVED" : "REJECTED";
        throw new IllegalArgumentException("Request stage " + stage + " is not actionable");
    }

    public static BigDecimal discountFee(BigDecimal amount, int tenor) {
        return amount.multiply(RATE).multiply(BigDecimal.valueOf(tenor)).divide(BigDecimal.valueOf(360), 2, RoundingMode.HALF_UP);
    }
    public static BigDecimal processingFee() { return new BigDecimal("50.00"); }
    public static BigDecimal netPayout(BigDecimal amount, int tenor) {
        return amount.subtract(discountFee(amount, tenor)).subtract(processingFee()).setScale(2, RoundingMode.HALF_UP);
    }
}
