INSERT INTO invoices VALUES
('I-101','INV-2026-101','APPROVED','USD',120000,0),
('I-102','INV-2026-102','APPROVED','USD',80000,0),
('I-103','INV-2026-103','APPROVED','EUR',95000,0),
('I-104','INV-2026-104','APPROVED','USD',60000,60000),
('I-105','INV-2026-105','PENDING_APPROVAL','USD',45000,0),
('I-106','INV-2026-106','APPROVED','GBP',50000,0);
INSERT INTO beneficiaries VALUES
('BEN-US-001','Apex US Treasury Account','USD'),
('BEN-US-123','Citibank NA Commercial Clearing','USD'),
('BEN-EU-101','Deutsche Bank SEPA Settlement','EUR');
INSERT INTO drawdown_requests(ref,submission_token,currency,requested_amount,discount_fee,processing_fee,net_payout,tenor_days,beneficiary_code,terms_acknowledged,created_at,created_by,approval_stage,checker1_by,checker2_by)
VALUES ('REQ-2026-0001','seed-token','USD',180000,2700,50,177250,90,'BEN-US-001',TRUE,CURRENT_TIMESTAMP,'maker-1','APPROVED','checker-1','checker-2');
INSERT INTO request_invoices VALUES ('REQ-2026-0001','INV-2026-104');
