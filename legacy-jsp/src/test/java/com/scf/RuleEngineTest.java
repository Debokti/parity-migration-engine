package com.scf;

import com.scf.domain.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RuleEngineTest {
    private Invoice usd(String ref, String status, BigDecimal financed) { return new Invoice(ref,status,"USD",new BigDecimal("10000"),financed); }
    @Test void eligibilityReasonsAreDeterministic() {
        assertEquals("ELIGIBLE", usd("a","APPROVED",BigDecimal.ZERO).eligibility());
        assertEquals("ALREADY_FINANCED", usd("b","APPROVED",BigDecimal.ONE).eligibility());
        assertEquals("NOT_APPROVED", usd("c","PENDING_APPROVAL",BigDecimal.ZERO).eligibility());
        assertEquals("UNSUPPORTED_CURRENCY", new Invoice("d","APPROVED","GBP",BigDecimal.TEN,BigDecimal.ZERO).eligibility());
    }
    @Test void exactAdvanceBoundaryIsAccepted() {
        DrawdownDraft d=valid(List.of("a")); d.requestedAmount=new BigDecimal("8500.00");
        assertFalse(RuleEngine.validate(d,List.of(usd("a","APPROVED",BigDecimal.ZERO)),new BigDecimal("320000")).containsKey("requestedAmount"));
    }
    @Test void feesRoundForAllTenors() {
        assertEquals(new BigDecimal("500.00"),RuleEngine.discountFee(new BigDecimal("100000"),30));
        assertEquals(new BigDecimal("1000.00"),RuleEngine.discountFee(new BigDecimal("100000"),60));
        assertEquals(new BigDecimal("1500.00"),RuleEngine.discountFee(new BigDecimal("100000"),90));
        assertEquals(new BigDecimal("98450.00"),RuleEngine.netPayout(new BigDecimal("100000"),90));
    }
    @Test void currencyMismatchIsRejected() {
        DrawdownDraft d=valid(List.of("a","b"));d.currency="USD";
        assertTrue(RuleEngine.validate(d,List.of(usd("a","APPROVED",BigDecimal.ZERO),new Invoice("b","APPROVED","EUR",BigDecimal.TEN,BigDecimal.ZERO)),new BigDecimal("320000")).containsKey("currency"));
    }
    @Test void attachmentAndTermsAreRequired() {
        DrawdownDraft d=valid(List.of("a"));
        Map<String,String> errors=RuleEngine.validate(d,List.of(usd("a","APPROVED",BigDecimal.ZERO)),new BigDecimal("320000"));
        assertTrue(errors.containsKey("attachments")); assertTrue(errors.containsKey("termsAcknowledged"));
    }
    @Test void nextStageTransitions() {
        assertEquals("PENDING_CHECKER_2", RuleEngine.nextStage("PENDING_CHECKER_1", "APPROVE"));
        assertEquals("REJECTED", RuleEngine.nextStage("PENDING_CHECKER_1", "REJECT"));
        assertEquals("APPROVED", RuleEngine.nextStage("PENDING_CHECKER_2", "APPROVE"));
        assertEquals("REJECTED", RuleEngine.nextStage("PENDING_CHECKER_2", "REJECT"));
        assertThrows(IllegalArgumentException.class, () -> RuleEngine.nextStage("PENDING_CHECKER_1", "HOLD"));
        assertThrows(IllegalArgumentException.class, () -> RuleEngine.nextStage("APPROVED", "APPROVE"));
    }
    @Test void invoiceBeanGettersExposeRecordState() {
        Invoice i = new Invoice("r", "APPROVED", "USD", new BigDecimal("10"), BigDecimal.ZERO);
        assertEquals("r", i.getRef()); assertEquals("APPROVED", i.getStatus());
        assertEquals("USD", i.getCurrency()); assertEquals(new BigDecimal("10"), i.getAmount());
        assertEquals(BigDecimal.ZERO, i.getFinancedAmount()); assertEquals("ELIGIBLE", i.getEligibility());
    }
    private DrawdownDraft valid(List<String> refs){DrawdownDraft d=new DrawdownDraft();d.invoiceRefs=new ArrayList<>(refs);d.currency="USD";d.requestedAmount=new BigDecimal("5000");d.tenorDays=30;d.beneficiaryCode="BEN-US-001";return d;}
}
