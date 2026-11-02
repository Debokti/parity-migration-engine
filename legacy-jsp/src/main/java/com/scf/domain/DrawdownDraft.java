package com.scf.domain;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

public class DrawdownDraft {
    public List<String> invoiceRefs = new ArrayList<>();
    public BigDecimal requestedAmount;
    public String currency;
    public Integer tenorDays;
    public String beneficiaryCode;
    public boolean termsAcknowledged;
    public String submissionToken;
    public List<Attachment> attachments = new ArrayList<>();
}
