import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import {
  DrawdownComponent,
  InvoiceCheckboxRendererComponent,
  detectEmbedMode
} from './drawdown.component';
import {
  MFE_ELEMENT_NAME,
  bootstrapStandalone,
  mountNorthstarDrawdownMfe,
  registerDrawdownMfe
} from './mfe-mount';

describe('DrawdownComponent', () => {
  let fixture: ComponentFixture<DrawdownComponent>;
  let component: DrawdownComponent;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    delete (window as unknown as Record<string, unknown>)['__PARITY_MFE_EMBEDDED__'];
    TestBed.configureTestingModule({
      imports: [DrawdownComponent, HttpClientTestingModule]
    });
    fixture = TestBed.createComponent(DrawdownComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    fixture.destroy();
    sessionStorage.clear();
    delete (window as unknown as Record<string, unknown>)['__PARITY_MFE_CONTEXT__'];
  });

  function flushInit(): void {
    httpMock.expectOne('/api/v1/auth/bridge').flush({
      token: 'test-token', sessionId: 's1', actorId: 'maker-1', role: 'MAKER_1'
    });
    httpMock.expectOne('/api/v1/dashboard').flush({
      supplierId: 'SUP-10042', supplierName: 'Apex Industrial Components Ltd.',
      programStatus: 'ACTIVE', facilityLimit: 500000, utilizedAmount: 181000, availableLimit: 319000
    });
    httpMock.expectOne('/api/v1/requests').flush([]);
  }

  function seedDraftStorage(): void {
    sessionStorage.setItem('SCF_DRAFT_REQUEST', JSON.stringify({
      invoiceRefs: ['INV-2026-101'], requestedAmount: 5000, currency: 'USD',
      tenorDays: 30, beneficiaryCode: 'BEN-US-001'
    }));
  }

  it('creates the component', () => {
    fixture.detectChanges();
    flushInit();
    expect(component).toBeTruthy();
    expect(component.actorId()).toBe('maker-1');
  });

  describe('isolated embed mode', () => {
    it('detects the embed query param and the federated-mount flag', () => {
      expect(detectEmbedMode('?embed=1', undefined)).toBe(true);
      expect(detectEmbedMode('?embed=1&x=y', undefined)).toBe(true);
      expect(detectEmbedMode('', undefined)).toBe(false);
      expect(detectEmbedMode('?embed=0', undefined)).toBe(false);
      expect(detectEmbedMode('', true)).toBe(true);
    });

    it('shows the navigation menu standalone', () => {
      fixture.detectChanges();
      flushInit();
      expect(component.embedded()).toBe(false);
      expect(fixture.nativeElement.querySelector('.sideNav')).not.toBeNull();
    });

    it('hides the navigation menu but keeps the drawdown form when embedded', () => {
      fixture.detectChanges();
      flushInit();
      component.embedded.set(true);
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('.sideNav')).toBeNull();
      expect(fixture.nativeElement.querySelector('[data-testid="submit-review"]')).not.toBeNull();
      expect(fixture.nativeElement.querySelector('[data-testid="auth-bridge-status"]')).not.toBeNull();
    });
  });

  describe('advance cap and fee math', () => {
    it('maxAdvanceable is zero with no selection', () => {
      expect(component.maxAdvanceable()).toBe(0);
    });

    it('maxAdvanceable applies the 85% cap', () => {
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      expect(component.maxAdvanceable()).toBe(102000);
      component.selectedInvoiceRefs.set(['INV-2026-101', 'INV-2026-102']);
      expect(component.maxAdvanceable()).toBe(170000);
    });

    it('discountFee returns zero without amount or tenor', () => {
      expect(component.discountFee()).toBe(0);
      component.requestedAmount.set(1000);
      expect(component.discountFee()).toBe(0);
    });

    it('discountFee uses 6% annual over 360 days with half-up rounding', () => {
      component.requestedAmount.set(1000);
      component.tenorDays.set(30);
      expect(component.discountFee()).toBe(5);
      component.requestedAmount.set(999);
      expect(component.discountFee()).toBe(5);
    });

    it('processingFee is a flat 50', () => {
      expect(component.processingFee()).toBe(50);
    });

    it('netPayout subtracts discount and processing fees', () => {
      expect(component.netPayout()).toBe(0);
      component.requestedAmount.set(1000);
      component.tenorDays.set(30);
      expect(component.netPayout()).toBe(945);
    });
  });

  describe('validation errors', () => {
    it('emits nothing on a pristine draft', () => {
      expect(component.validationErrors()).toEqual([]);
    });

    it('flags ineligible and unknown invoices', () => {
      component.selectedInvoiceRefs.set(['INV-2026-104']);
      expect(component.validationErrors()).toContain('invoiceRefs: One or more invoices are not eligible');
      component.selectedInvoiceRefs.set(['INV-2026-999']);
      expect(component.validationErrors()).toContain('invoiceRefs: One or more invoices are not eligible');
    });

    it('flags unsupported and mismatched currency', () => {
      component.currency.set('GBP');
      expect(component.validationErrors()).toContain('Currency must be USD or EUR');
      component.currency.set('EUR');
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      expect(component.validationErrors()).toContain('Selected invoices must match request currency');
    });

    it('flags amounts outside 1000..cap with the exact cap text', () => {
      component.selectedInvoiceRefs.set(['INV-2026-101', 'INV-2026-102']);
      component.requestedAmount.set(500);
      expect(component.validationErrors()).toContain(
        'requestedAmount: Amount must be between 1,000.00 and 170000.00');
      component.requestedAmount.set(200000);
      expect(component.validationErrors()).toContain(
        'requestedAmount: Amount must be between 1,000.00 and 170000.00');
    });

    it('flags amounts above the available program limit', () => {
      component.selectedInvoiceRefs.set(component.invoices.map(i => i.ref));
      component.requestedAmount.set(330000);
      expect(component.validationErrors()).toContain('Amount exceeds available program limit');
    });

    it('flags bad tenor and beneficiary codes', () => {
      component.tenorDays.set(45);
      expect(component.validationErrors()).toContain('Tenor must be 30, 60, or 90 days');
      component.beneficiaryCode.set('BAD');
      expect(component.validationErrors()).toContain('Enter a valid beneficiary code');
    });

    it('requires an INVOICE_COPY attachment once a draft is persisted', () => {
      seedDraftStorage();
      component.requestedAmount.set(5000);
      expect(component.validationErrors()).toContain('At least one INVOICE_COPY attachment is required');
      component.attachments.set([{ category: 'INVOICE_COPY', filename: 'a.pdf', fileType: 'application/pdf', sizeBytes: 10 }]);
      expect(component.validationErrors()).not.toContain('At least one INVOICE_COPY attachment is required');
    });

    it('does not require attachments before a draft exists', () => {
      component.requestedAmount.set(5000);
      expect(component.validationErrors()).not.toContain('At least one INVOICE_COPY attachment is required');
    });
  });

  describe('display errors', () => {
    it('shows the terms message after a submit attempt', () => {
      component.submitAttempted.set(true);
      expect(component.displayErrors()).toContain('Terms must be acknowledged');
      component.termsAcknowledged.set(true);
      expect(component.displayErrors()).not.toContain('Terms must be acknowledged');
    });

    it('unshifts the select-invoice message first', () => {
      component.submitAttempted.set(true);
      expect(component.displayErrors()[0]).toBe('Select at least one invoice');
    });

    it('merges server messages verbatim without duplicates', () => {
      component.currency.set('GBP');
      component.serverValidationMessages.set(['Currency must be USD or EUR', 'Custom server note']);
      const shown = component.displayErrors();
      expect(shown).toContain('Custom server note');
      expect(shown.filter(m => m === 'Currency must be USD or EUR').length).toBe(1);
    });
  });

  describe('tokens, toggles, and draft helpers', () => {
    it('ensureToken keeps an existing token', () => {
      component.submissionToken.set('keep-me');
      component.ensureToken();
      expect(component.submissionToken()).toBe('keep-me');
    });

    it('ensureToken mints the deterministic golden token', () => {
      component.ensureToken();
      expect(component.submissionToken()).toBe('golden-valid-e851d76f');
      expect(sessionStorage.getItem('submissionToken')).toBe('golden-valid-e851d76f');
    });

    it('ensureToken reuses a stored submission token', () => {
      sessionStorage.setItem('submissionToken', 'stored-1');
      component.ensureToken();
      expect(component.submissionToken()).toBe('stored-1');
    });

    it('ensureToken patches a persisted draft token', () => {
      sessionStorage.setItem('SCF_DRAFT_REQUEST', JSON.stringify({ invoiceRefs: [] }));
      component.ensureToken();
      expect(JSON.parse(sessionStorage.getItem('SCF_DRAFT_REQUEST') ?? '{}').submissionToken)
        .toBe('golden-valid-e851d76f');
    });

    it('onInvoiceToggle adds, dedupes, and removes refs', () => {
      component.onInvoiceToggle('INV-2026-101', true);
      component.onInvoiceToggle('INV-2026-101', true);
      expect(component.selectedInvoiceRefs()).toEqual(['INV-2026-101']);
      component.onInvoiceToggle('INV-2026-101', false);
      expect(component.selectedInvoiceRefs()).toEqual([]);
    });

    it('hasDraftPersisted detects empty, corrupt, partial, and full drafts', () => {
      expect(component.hasDraftPersisted()).toBe(false);
      sessionStorage.setItem('SCF_DRAFT_REQUEST', '###');
      expect(component.hasDraftPersisted()).toBe(false);
      sessionStorage.setItem('SCF_DRAFT_REQUEST', JSON.stringify({ invoiceRefs: ['INV-2026-101'] }));
      expect(component.hasDraftPersisted()).toBe(false);
      seedDraftStorage();
      expect(component.hasDraftPersisted()).toBe(true);
    });

    it('restores signals from sessionStorage on init', () => {
      seedDraftStorage();
      sessionStorage.setItem('submissionToken', 'tok-restore');
      fixture.detectChanges();
      flushInit();
      expect(component.selectedInvoiceRefs()).toEqual(['INV-2026-101']);
      expect(component.requestedAmount()).toBe(5000);
      expect(component.submissionToken()).toBe('tok-restore');
    });
  });

  describe('InvoiceCheckboxRendererComponent', () => {
    it('renders the ref testid with live selection state', () => {
      const renderer = new InvoiceCheckboxRendererComponent();
      const toggles: Array<[string, boolean]> = [];
      renderer.agInit({
        data: { ref: 'INV-2026-101', status: 'APPROVED', currency: 'USD', amount: 1, financedAmount: 0, eligibility: 'ELIGIBLE' },
        isSelected: (ref: string) => ref === 'INV-2026-101',
        onToggle: (ref: string, checked: boolean) => toggles.push([ref, checked])
      });
      expect(renderer.ref).toBe('INV-2026-101');
      expect(renderer.checked).toBe(true);
      expect(renderer.refresh()).toBe(true);
      renderer.onToggle({ target: { checked: false } } as unknown as Event);
      expect(renderer.checked).toBe(false);
      expect(toggles).toEqual([['INV-2026-101', false]]);
    });

    it('tolerates missing data and callbacks', () => {
      const renderer = new InvoiceCheckboxRendererComponent();
      renderer.agInit({});
      expect(renderer.ref).toBe('');
      expect(renderer.checked).toBe(false);
      expect(renderer.refresh()).toBe(true);
      renderer.onToggle({ target: { checked: true } } as unknown as Event);
      expect(renderer.checked).toBe(true);
    });
  });

  describe('invoice submission', () => {
    it('returns early with no selection', async () => {
      fixture.detectChanges();
      flushInit();
      await component.submitInvoices();
      expect(component.submitAttempted()).toBe(true);
    });

    it('posts urlencoded refs and surfaces server validation', async () => {
      fixture.detectChanges();
      flushInit();
      component.selectedInvoiceRefs.set(['INV-2026-101', 'INV-2026-102']);
      const done = component.submitInvoices();
      const req = httpMock.expectOne('/invoices/select');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toBe('invoiceRefs=INV-2026-101&invoiceRefs=INV-2026-102');
      req.flush('{"validationMessages":["invoiceRefs: One or more invoices are not eligible"]}');
      await done;
      expect(component.serverValidationMessages())
        .toContain('invoiceRefs: One or more invoices are not eligible');
      expect(component.submitAttempted()).toBe(false);
    });

    it('parses plain-text ineligible responses', async () => {
      fixture.detectChanges();
      flushInit();
      component.selectedInvoiceRefs.set(['INV-2026-104']);
      const done = component.submitInvoices();
      httpMock.expectOne('/invoices/select').flush('invoiceRefs: One or more invoices are not eligible');
      await done;
      expect(component.serverValidationMessages())
        .toContain('invoiceRefs: One or more invoices are not eligible');
    });

    it('tolerates transport errors', async () => {
      fixture.detectChanges();
      flushInit();
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      const done = component.submitInvoices();
      httpMock.expectOne('/invoices/select').error(new ErrorEvent('network down'));
      await done;
      expect(component.submitAttempted()).toBe(false);
    });
  });

  describe('draft storage keeps termsAcknowledged', () => {
    function storedDraft(): Record<string, unknown> {
      return JSON.parse(sessionStorage.getItem('SCF_DRAFT_REQUEST') ?? '{}');
    }

    it('submitInvoices persists the live terms boolean without a later effect run', async () => {
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      component.termsAcknowledged.set(true);
      fixture.detectChanges();
      flushInit();
      const done = component.submitInvoices();
      httpMock.expectOne('/invoices/select').flush('ok');
      await done;
      expect(storedDraft()['termsAcknowledged']).toBe(true);
      expect(storedDraft()['invoiceRefs']).toEqual(['INV-2026-101']);
    });

    it('submitDrawdown persists the live terms boolean without a later effect run', async () => {
      component.selectedInvoiceRefs.set(['INV-2026-101', 'INV-2026-102']);
      component.requestedAmount.set(5000);
      component.currency.set('USD');
      component.tenorDays.set(30);
      component.beneficiaryCode.set('BEN-US-001');
      component.termsAcknowledged.set(true);
      fixture.detectChanges();
      flushInit();
      const done = component.submitDrawdown();
      httpMock.expectOne('/review').flush('ok');
      await done;
      expect(storedDraft()['termsAcknowledged']).toBe(true);
    });
  });

  describe('drawdown submission', () => {
    it('blocks on validation errors without HTTP', async () => {
      fixture.detectChanges();
      flushInit();
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      component.requestedAmount.set(999999);
      component.currency.set('USD');
      component.tenorDays.set(30);
      component.beneficiaryCode.set('BEN-US-001');
      await component.submitDrawdown();
      expect(httpMock.match(() => true).length).toBe(0);
    });

    it('posts the urlencoded payload and persists the draft', async () => {
      fixture.detectChanges();
      flushInit();
      component.selectedInvoiceRefs.set(['INV-2026-101', 'INV-2026-102']);
      component.requestedAmount.set(5000);
      component.currency.set('USD');
      component.tenorDays.set(30);
      component.beneficiaryCode.set('BEN-US-001');
      const done = component.submitDrawdown();
      const req = httpMock.expectOne('/review');
      expect(req.request.body).toContain('requestedAmount=5000');
      expect(req.request.body).toContain('beneficiaryCode=BEN-US-001');
      req.flush('ok');
      await done;
      expect(component.submitAttempted()).toBe(false);
      expect(JSON.parse(sessionStorage.getItem('SCF_DRAFT_REQUEST') ?? '{}').currency).toBe('USD');
    });
  });

  describe('attachments', () => {
    it('returns early without category or filename', async () => {
      fixture.detectChanges();
      flushInit();
      await component.submitAttachment();
      expect(httpMock.match(() => true).length).toBe(0);
      expect(component.attachments().length).toBe(0);
    });

    it('shows a message instead of silently ignoring an empty attachment submit', async () => {
      fixture.detectChanges();
      flushInit();
      await component.submitAttachment();
      expect(component.displayErrors()).toContain('Filename is required to add an attachment');
      component.attachmentFilename.set('invoice-copy.pdf');
      component.attachmentFileType.set('application/pdf');
      component.attachmentSizeBytes.set(48210);
      const done = component.submitAttachment();
      httpMock.expectOne('/attachments').flush('ok');
      httpMock.expectOne('/api/v1/draft/attachments').flush({});
      await done;
      expect(component.attachments().length).toBe(1);
      expect(component.displayErrors()).not.toContain('Filename is required to add an attachment');
    });

    it('posts the form and JSON payloads then records the attachment', async () => {
      fixture.detectChanges();
      flushInit();
      component.attachmentFilename.set('invoice-copy.pdf');
      component.attachmentFileType.set('application/pdf');
      component.attachmentSizeBytes.set(48210);
      const done = component.submitAttachment();
      const form = httpMock.expectOne('/attachments');
      expect(form.request.body).toContain('filename=invoice-copy.pdf');
      form.flush('ok');
      const api = httpMock.expectOne('/api/v1/draft/attachments');
      expect(api.request.body).toEqual({
        category: 'INVOICE_COPY', filename: 'invoice-copy.pdf',
        fileType: 'application/pdf', sizeBytes: 48210
      });
      api.flush({});
      await done;
      expect(component.attachments().length).toBe(1);
    });
  });

  describe('draft sync and review submit', () => {
    it('syncs the draft with auth and anti-cache headers', async () => {
      fixture.detectChanges();
      flushInit();
      component.bearerToken.set('tok-1');
      component.selectedInvoiceRefs.set(['INV-2026-101']);
      const done = component.syncDraftReview();
      const req = httpMock.expectOne('/api/v1/draft');
      expect(req.request.method).toBe('PUT');
      expect(req.request.headers.get('Authorization')).toBe('Bearer tok-1');
      expect(req.request.headers.get('X-Actor-Id')).toBe('maker-1');
      expect(req.request.headers.get('X-Actor-Role')).toBe('MAKER_1');
      expect(req.request.headers.get('Cache-Control')).toBe('no-cache, no-store, must-revalidate');
      expect(req.request.headers.get('Pragma')).toBe('no-cache');
      expect(req.request.withCredentials).toBe(true);
      expect(req.request.body).toEqual(jasmine.objectContaining({
        termsAcknowledged: true, submissionToken: 'golden-valid-e851d76f'
      }));
      req.flush({});
      await done;
    });

    it('submitReview requires terms and an attachment', async () => {
      fixture.detectChanges();
      flushInit();
      await component.submitReview();
      component.termsAcknowledged.set(true);
      await component.submitReview();
      expect(component.confirmation()).toBe('');
      expect(httpMock.match(() => true).length).toBe(0);
    });

    it('submitReview posts and writes the confirmation', async () => {
      fixture.detectChanges();
      flushInit();
      component.termsAcknowledged.set(true);
      component.attachments.set([{ category: 'INVOICE_COPY', filename: 'a.pdf', fileType: 'application/pdf', sizeBytes: 1 }]);
      component.requestedAmount.set(1000);
      component.tenorDays.set(30);
      component.currency.set('USD');
      const done = component.submitReview();
      const req = httpMock.expectOne('/review/submit');
      expect(req.request.body).toContain('termsAcknowledged=on');
      req.flush('ok');
      const reload = httpMock.expectOne('/api/v1/requests');
      reload.flush([]);
      await done;
      expect(component.confirmation()).toContain('Drawdown confirmed REQ-');
      expect(component.confirmation()).toContain('Net payout 945.00 USD');
    });
  });

  describe('auth bridge and MFE context', () => {
    it('adopts a full MFE context', () => {
      component.adoptMfeContext({
        sessionId: 's9', bearerToken: 'bearer-9', actor: { id: 'checker-2', role: 'CHECKER_2' }
      });
      expect(component.bearerToken()).toBe('bearer-9');
      expect(component.bridgeSessionId()).toBe('s9');
      expect(component.actorId()).toBe('checker-2');
      expect(component.actorRole()).toBe('CHECKER_2');
      expect(component.bridgeStatusText()).toBe('JSESSIONID <-> Bearer Synced');
    });

    it('adopts an empty MFE context with maker defaults', () => {
      component.adoptMfeContext({});
      expect(component.actorId()).toBe('maker-1');
      expect(component.actorRole()).toBe('MAKER_1');
      expect(component.bridgeOk()).toBe(false);
      expect(component.bridgeStatusText()).toBe('Bridge Disconnected');
    });

    it('derives checker roles from actor ids', () => {
      component.adoptMfeContext({ bearerToken: 't', actor: { id: 'checker-1' } });
      expect(component.actorRole()).toBe('CHECKER_1');
    });

    it('skips the bridge call when embedded with a popup context', () => {
      (window as unknown as Record<string, unknown>)['__PARITY_MFE_CONTEXT__'] = {
        sessionId: 'popup-s', bearerToken: 'popup-b', actor: { id: 'checker-1', role: 'CHECKER_1' }
      };
      fixture.detectChanges();
      expect(httpMock.match('/api/v1/auth/bridge').length).toBe(0);
      expect(component.bearerToken()).toBe('popup-b');
      httpMock.expectOne('/api/v1/dashboard').flush({});
      httpMock.expectOne('/api/v1/requests').flush([]);
    });

    it('handshake events adopt and ignore empty contexts', () => {
      component.handshakeListener(new CustomEvent('parity:auth-handshake', {
        detail: { bearerToken: 'hs-1', actor: { id: 'maker-1', role: 'MAKER_1' } }
      }));
      expect(component.bearerToken()).toBe('hs-1');
      component.handshakeListener(new CustomEvent('parity:auth-handshake'));
      expect(component.bearerToken()).toBe('hs-1');
    });

    it('bridge stores the minted token and actor', async () => {
      fixture.detectChanges();
      const req = httpMock.expectOne('/api/v1/auth/bridge');
      expect(req.request.withCredentials).toBe(true);
      req.flush({ token: 'mint-1', sessionId: 's-m', actorId: 'checker-1', role: 'CHECKER_1' });
      httpMock.expectOne('/api/v1/dashboard').flush({});
      httpMock.expectOne('/api/v1/requests').flush([]);
      await fixture.whenStable();
      expect(component.bearerToken()).toBe('mint-1');
      expect(component.actorRole()).toBe('CHECKER_1');
    });

    it('bridge surfaces failures on the badge', async () => {
      fixture.detectChanges();
      httpMock.expectOne('/api/v1/auth/bridge').flush('boom', { status: 500, statusText: 'error' });
      httpMock.expectOne('/api/v1/dashboard').flush({});
      httpMock.expectOne('/api/v1/requests').flush([]);
      await fixture.whenStable();
      expect(component.bridgeError()).toContain('boom');
      expect(component.bridgeStatusText()).toContain('Bridge Error');
    });
  });

  describe('heartbeat', () => {
    it('startHeartbeat schedules the configured interval', () => {
      const spy = spyOn(window, 'setInterval').and.callThrough();
      component.heartbeatIntervalMs = 1234;
      component.startHeartbeat();
      expect(spy).toHaveBeenCalledWith(jasmine.any(Function), 1234);
      component.stopHeartbeat();
    });

    it('stopHeartbeat clears a running timer', () => {
      component.startHeartbeat();
      expect((component as unknown as { heartbeatTimer: unknown }).heartbeatTimer).not.toBeNull();
      component.stopHeartbeat();
      expect((component as unknown as { heartbeatTimer: unknown }).heartbeatTimer).toBeNull();
    });

    it('doHeartbeat skips without a token', async () => {
      await component.doHeartbeat();
      expect(httpMock.match(() => true).length).toBe(0);
    });

    it('doHeartbeat records valid heartbeats', async () => {
      component.bearerToken.set('tok-hb');
      const done = component.doHeartbeat();
      const req = httpMock.expectOne('/api/v1/auth/heartbeat');
      expect(req.request.headers.get('Authorization')).toBe('Bearer tok-hb');
      req.flush({ valid: true, remainingTtlSeconds: 1700 });
      await done;
      expect(component.lastHeartbeat()).not.toBeNull();
    });

    it('doHeartbeat re-bridges on invalid or failed heartbeats', async () => {
      fixture.detectChanges();
      flushInit();
      const first = component.doHeartbeat();
      httpMock.expectOne('/api/v1/auth/heartbeat').flush({ valid: false });
      httpMock.expectOne('/api/v1/auth/bridge').flush({ token: 're-1' });
      await first;
      expect(component.bearerToken()).toBe('re-1');
      const second = component.doHeartbeat();
      httpMock.expectOne('/api/v1/auth/heartbeat').flush('gone', { status: 401, statusText: 'x' });
      httpMock.expectOne('/api/v1/auth/bridge').flush({ token: 're-2' });
      await second;
      expect(component.bearerToken()).toBe('re-2');
    });
  });

  describe('actor switching', () => {
    it('switches actor, re-bridges, and reloads requests', async () => {
      fixture.detectChanges();
      flushInit();
      const done = component.switchActor('checker-2');
      const req = httpMock.expectOne('/api/v1/actor');
      expect(req.request.body).toEqual({ actorId: 'checker-2' });
      req.flush({ actorId: 'checker-2', role: 'CHECKER_2' });
      httpMock.expectOne('/api/v1/auth/bridge').flush({ token: 'tok-c2' });
      httpMock.expectOne('/api/v1/requests').flush([{ ref: 'REQ-1' }]);
      await done;
      expect(component.actorId()).toBe('checker-2');
      expect(component.bearerToken()).toBe('tok-c2');
      expect(component.requests().length).toBe(1);
    });

    it('surfaces actor switch failures', async () => {
      fixture.detectChanges();
      flushInit();
      const done = component.switchActor('');
      httpMock.expectOne('/api/v1/actor').flush('actorId is required', { status: 400, statusText: 'x' });
      await done;
      expect(component.actionMessage()).toContain('Actor switch failed');
    });
  });

  describe('dashboard and request history', () => {
    it('loads the dashboard and formats the supplier line', async () => {
      fixture.detectChanges();
      httpMock.expectOne('/api/v1/auth/bridge').flush({ token: 't' });
      httpMock.expectOne('/api/v1/dashboard').flush({
        supplierId: 'SUP-10042', supplierName: 'Apex Industrial Components Ltd.',
        programStatus: 'ACTIVE', facilityLimit: 500000, utilizedAmount: 185000, availableLimit: 315000
      });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await fixture.whenStable();
      expect(component.supplierLine()).toBe('SUP-10042 — Apex Industrial Components Ltd. — ACTIVE');
      expect(component.dashboardData()?.availableLimit).toBe(315000);
    });

    it('falls back to the static supplier card offline', async () => {
      fixture.detectChanges();
      httpMock.expectOne('/api/v1/auth/bridge').flush({ token: 't' });
      httpMock.expectOne('/api/v1/dashboard').flush('down', { status: 500, statusText: 'x' });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await fixture.whenStable();
      expect(component.dashboardError()).toContain('down');
      expect(component.supplierLine()).toBe('SUP-10042 — Apex Industrial Components Ltd. — ACTIVE');
    });

    it('loads requests and coerces non-arrays to empty', async () => {
      fixture.detectChanges();
      flushInit();
      const rows = [{ ref: 'REQ-1', approvalStage: 'PENDING_CHECKER_1' }];
      const first = component.loadRequests();
      httpMock.expectOne('/api/v1/requests').flush(rows);
      await first;
      expect(component.requests()).toEqual(rows as never);
      const second = component.loadRequests();
      httpMock.expectOne('/api/v1/requests').flush({} as never);
      await second;
      expect(component.requests()).toEqual([]);
    });

    it('surfaces request load failures', async () => {
      fixture.detectChanges();
      flushInit();
      const done = component.loadRequests();
      httpMock.expectOne('/api/v1/requests').flush('nope', { status: 500, statusText: 'x' });
      await done;
      expect(component.requestsError()).toContain('nope');
    });

    it('selectRequest tracks the ref and clears messages', () => {
      component.actionMessage.set('stale');
      component.selectRequest('REQ-9');
      expect(component.selectedRequestRef()).toBe('REQ-9');
      expect(component.actionMessage()).toBe('');
    });
  });

  describe('4-eyes governance gates', () => {
    const row = (stage: string) => ({
      ref: 'REQ-1', currency: 'USD', requestedAmount: 5000, tenorDays: 30,
      beneficiaryCode: 'BEN-US-001', approvalStage: stage
    });

    it('gates amend to makers with a selection', () => {
      expect(component.canAmend()).toBe(false);
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      expect(component.canAmend()).toBe(true);
      component.actorRole.set('CHECKER_1');
      expect(component.canAmend()).toBe(false);
    });

    it('gates checker actions by role and stage', () => {
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      component.actorRole.set('CHECKER_1');
      expect(component.canChecker1()).toBe(true);
      expect(component.canChecker2()).toBe(false);
      component.requests.set([row('PENDING_CHECKER_2')]);
      component.actorRole.set('CHECKER_2');
      expect(component.canChecker1()).toBe(false);
      expect(component.canChecker2()).toBe(true);
      component.requests.set([row('APPROVED')]);
      expect(component.canChecker2()).toBe(false);
    });

    it('amendSelected requires a selection and at least one field', async () => {
      await component.amendSelected();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      await component.amendSelected();
      expect(component.actionMessage()).toContain('Nothing to amend');
      expect(httpMock.match(() => true).length).toBe(0);
    });

    it('amendSelected puts partial fields and reloads', async () => {
      fixture.detectChanges();
      flushInit();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      component.amendAmount.set(6000);
      component.amendTenor.set(60);
      const done = component.amendSelected();
      const req = httpMock.expectOne('/api/v1/requests/REQ-1/amend');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ requestedAmount: 6000, tenorDays: 60 });
      req.flush({ approvalStage: 'PENDING_CHECKER_1' });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await done;
      expect(component.actionMessage()).toBe('Amended REQ-1: PENDING_CHECKER_1');
    });

    it('amendSelected joins map-shaped validation errors', async () => {
      fixture.detectChanges();
      flushInit();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      component.amendAmount.set(999999);
      const done = component.amendSelected();
      httpMock.expectOne('/api/v1/requests/REQ-1/amend')
        .flush({ errors: { requestedAmount: 'too big' } }, { status: 400, statusText: 'x' });
      await done;
      expect(component.actionMessage()).toContain('Amend failed: too big');
    });

    it('checkerSelected approves and rejects with reasons', async () => {
      fixture.detectChanges();
      flushInit();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      const approve = component.checkerSelected(1, 'APPROVE');
      const req1 = httpMock.expectOne('/api/v1/requests/REQ-1/checker1');
      expect(req1.request.body).toEqual({ action: 'APPROVE' });
      req1.flush({ approvalStage: 'PENDING_CHECKER_2' });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await approve;
      expect(component.actionMessage()).toBe('Checker1 APPROVE: PENDING_CHECKER_2');
      component.rejectReason.set('bad docs');
      const reject = component.checkerSelected(2, 'REJECT');
      const req2 = httpMock.expectOne('/api/v1/requests/REQ-1/checker2');
      expect(req2.request.body).toEqual({ action: 'REJECT', rejectionReason: 'bad docs' });
      req2.flush({ approvalStage: 'REJECTED' });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await reject;
      expect(component.actionMessage()).toBe('Checker2 REJECT: REJECTED');
    });

    it('checkerSelected requires a selection and surfaces failures', async () => {
      await component.checkerSelected(1, 'APPROVE');
      expect(httpMock.match(() => true).length).toBe(0);
      fixture.detectChanges();
      flushInit();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      const done = component.checkerSelected(1, 'APPROVE');
      httpMock.expectOne('/api/v1/requests/REQ-1/checker1')
        .flush({ message: 'stale stage' }, { status: 400, statusText: 'x' });
      await done;
      expect(component.actionMessage()).toContain('Checker1 APPROVE failed: stale stage');
    });

    it('surfaces empty error maps via the transport message', async () => {
      fixture.detectChanges();
      flushInit();
      component.requests.set([row('PENDING_CHECKER_1')]);
      component.selectedRequestRef.set('REQ-1');
      component.amendAmount.set(6000);
      const done = component.amendSelected();
      httpMock.expectOne('/api/v1/requests/REQ-1/amend')
        .flush({ errors: {} }, { status: 400, statusText: 'x' });
      await done;
      expect(component.actionMessage()).toContain('Amend failed: Http failure');
    });
  });

  describe('grid handlers', () => {
    it('gridReady stores the api and fits columns', () => {
      const invoiceApi = jasmine.createSpyObj('api', ['sizeColumnsToFit']);
      component.onInvoiceGridReady({ api: invoiceApi } as never);
      expect(invoiceApi.sizeColumnsToFit).toHaveBeenCalled();
      const requestsApi = jasmine.createSpyObj('api', ['sizeColumnsToFit']);
      component.onRequestsGridReady({ api: requestsApi } as never);
      expect(requestsApi.sizeColumnsToFit).toHaveBeenCalled();
    });

    it('row clicks select requests and ignore empty rows', () => {
      component.onRequestRowClicked({ data: { ref: 'REQ-7' } } as never);
      expect(component.selectedRequestRef()).toBe('REQ-7');
      component.onRequestRowClicked({});
      expect(component.selectedRequestRef()).toBe('REQ-7');
    });
  });

  describe('fetch fallback without HttpClient', () => {
    beforeEach(() => {
      (component as unknown as { http: null }).http = null;
    });

    it('loads requests over fetch', async () => {
      spyOn(window, 'fetch').and.resolveTo(
        new Response(JSON.stringify([{ ref: 'REQ-f' }]), { status: 200 }));
      await component.loadRequests();
      expect(component.requests().length).toBe(1);
    });

    it('reports fetch error bodies', async () => {
      spyOn(window, 'fetch').and.resolveTo(new Response('fetch-down', { status: 500 }));
      await component.loadRequests();
      expect(component.requestsError()).toBe('fetch-down');
    });

    it('falls back to the status text on empty error bodies', async () => {
      spyOn(window, 'fetch').and.resolveTo(new Response('', { status: 500 }));
      await component.loadRequests();
      expect(component.requestsError()).toBe('GET /api/v1/requests failed: 500');
    });

    it('sends JSON posts over fetch and tolerates rejections', async () => {
      component.requests.set([{ ref: 'REQ-1', currency: 'USD', requestedAmount: 1, tenorDays: 30, beneficiaryCode: 'b', approvalStage: 'PENDING_CHECKER_1' }]);
      component.selectedRequestRef.set('REQ-1');
      spyOn(window, 'fetch').and.resolveTo(
        new Response(JSON.stringify({ approvalStage: 'PENDING_CHECKER_2' }), { status: 200 }));
      await component.checkerSelected(1, 'APPROVE');
      expect(component.actionMessage()).toBe('Checker1 APPROVE: PENDING_CHECKER_2');
      (window.fetch as jasmine.Spy).and.rejectWith(new Error('net-down'));
      await component.checkerSelected(1, 'APPROVE');
      expect(component.actionMessage()).toContain('net-down');
    });
  });

  describe('file explorer, staging area, unselected warning popup, and ACK/NACK lock', () => {
    it('onFilesSelected stages multiple files from File Explorer and clears manual inputs', () => {
      const f1 = new File(['pdf-bytes'], 'inv-101.pdf', { type: '' });
      const f2 = new File(['png-bytes'], 'scan.png', { type: 'image/png' });
      const fakeEvent = { target: { files: [f1, f2] } } as unknown as Event;
      component.onFilesSelected(fakeEvent);
      expect(component.attachmentFilename()).toBe('');
      expect(component.stagedAttachments().length).toBe(2);
      expect(component.stagedAttachments()[0].filename).toBe('inv-101.pdf');
      expect(component.stagedAttachments()[0].fileType).toBe('application/pdf');
      expect(component.stagedAttachments()[0].selected).toBe(true);
      expect(component.stagedAttachments()[1].fileType).toBe('image/png');
    });

    it('stages manual inputs, views, and deletes staged files', () => {
      component.stageCurrentInput();
      expect(component.attachmentFormError()).toContain('Filename is required');
      component.attachmentFilename.set('contract.docx');
      component.stageCurrentInput();
      expect(component.stagedAttachments().length).toBe(1);
      expect(component.stagedAttachments()[0].fileType).toContain('wordprocessingml');
      component.viewAttachment(component.stagedAttachments()[0]);
      expect(component.viewedAttachment()?.filename).toBe('contract.docx');
      component.closeViewer();
      expect(component.viewedAttachment()).toBeNull();
      component.deleteStagedAttachment(0);
      expect(component.stagedAttachments().length).toBe(0);
    });

    it('opens confirmation popup when some staged files are unselected and discards unselected on continue', async () => {
      component.attachmentFilename.set('keep.pdf');
      component.stageCurrentInput();
      component.attachmentFilename.set('drop.jpg');
      component.stageCurrentInput();
      component.toggleStagedSelection(1, false);

      await component.confirmFinalUpload();
      expect(component.unselectedWarningOpen()).toBe(true);
      expect(component.attachments().length).toBe(0);

      component.cancelFinalUpload();
      expect(component.unselectedWarningOpen()).toBe(false);
      expect(component.stagedAttachments().length).toBe(2);

      await component.confirmFinalUpload();
      expect(component.unselectedWarningOpen()).toBe(true);
      await component.proceedFinalUpload();
      expect(component.unselectedWarningOpen()).toBe(false);
      expect(component.stagedAttachments().length).toBe(0);
      expect(component.attachments().length).toBe(1);
      expect(component.attachments()[0].filename).toBe('keep.pdf');
      expect(component.uploadConfirmed()).toBe(true);
    });

    it('locks confirmed uploads against deletion/revert by same user until ACK or NACK Maker-Checker completes', async () => {
      fixture.detectChanges();
      flushInit();
      component.attachmentFilename.set('locked.pdf');
      component.stageCurrentInput();
      await component.confirmFinalUpload();
      expect(component.unselectedWarningOpen()).toBe(true);
      expect(component.hasUnselectedStaged()).toBe(false);
      expect(component.selectedStagedCount()).toBe(1);
      await component.proceedFinalUpload();
      expect(component.attachments().length).toBe(1);
      expect(component.isUploadLockedForSameUser()).toBe(true);

      // Same user (maker-1) attempts to delete or revert before ACK/NACK
      component.deleteConfirmedAttachment(0);
      expect(component.attachments().length).toBe(1);
      expect(component.uploadLockError()).toContain('cannot be removed or reverted by the same user');

      component.revertConfirmedAttachments();
      expect(component.attachments().length).toBe(1);

      // Complete Maker-Checker with NACK (REJECTED) or ACK (APPROVED)
      component.requests.set([{
        ref: 'REQ-1', currency: 'USD', requestedAmount: 5000, tenorDays: 30,
        beneficiaryCode: 'BEN-US-001', approvalStage: 'PENDING_CHECKER_1'
      }]);
      component.selectedRequestRef.set('REQ-1');
      const rejectP = component.checkerSelected(1, 'REJECT');
      httpMock.expectOne('/api/v1/requests/REQ-1/checker1').flush({ approvalStage: 'REJECTED' });
      httpMock.expectOne('/api/v1/requests').flush([]);
      await rejectP;

      expect(component.makerCheckerAckNackCompleted()).toBe(true);
      expect(component.isUploadLockedForSameUser()).toBe(false);

      // Now deletion and revert succeed
      component.deleteConfirmedAttachment(0);
      expect(component.attachments().length).toBe(0);
      component.attachments.set([{ category: 'INVOICE_COPY', filename: 'x.pdf', fileType: 'application/pdf', sizeBytes: 1 }]);
      component.lockUploadedFiles();
      component.makerCheckerAckNackCompleted.set(true);
      component.revertConfirmedAttachments();
      expect(component.attachments().length).toBe(0);
    });
  });
});

describe('drawdown MFE mount hook', () => {
  it('registers the custom element and global exactly once', () => {
    registerDrawdownMfe();
    registerDrawdownMfe();
    expect(customElements.get(MFE_ELEMENT_NAME)).toBeTruthy();
    expect(typeof (window as unknown as Record<string, unknown>)['mountNorthstarDrawdownMfe']).toBe('function');
  });

  it('rejects mounts without a target', async () => {
    await expectAsync(mountNorthstarDrawdownMfe('#mfe-missing-target')).toBeRejectedWithError(
      'mount target not found');
  });

  it('bootstrapStandalone is safe without a root element', () => {
    document.querySelectorAll('app-drawdown').forEach(el => el.remove());
    expect(() => bootstrapStandalone()).not.toThrow();
  });

  it('mounts the live component into a host element', async () => {
    const host = document.createElement('div');
    host.id = 'mfe-live-host';
    document.body.appendChild(host);
    await mountNorthstarDrawdownMfe(host);
    const root = host.querySelector('app-drawdown');
    expect(root).toBeTruthy();
    host.remove();
  });
});
