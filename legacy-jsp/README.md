# Legacy JSP reference application

Commercial Supply Portal is a synthetic supplier-finance training
application. It requires Java 17+ and Maven 3.9+. It uses embedded Tomcat 9,
JSP/JSTL, Jackson, and an in-memory H2 database; no external application
server is required.

## Run

From this directory:

```powershell
mvn clean test
mvn compile exec:java
```

The server listens on `http://localhost:8080`; use
`-Dserver.port=8081` to choose another port. The database is initialized from
`src/main/resources/schema.sql` and `seed.sql`.

## Deterministic business rules

1. Only `APPROVED`, zero-financed invoices in USD or EUR are eligible.
2. Selected invoice currencies must match the request currency.
3. `maxAdvanceable = round(sum(invoice amounts) * 0.85, 2)`.
4. Requested amount is at least 1,000.00 and cannot exceed the cap or available
   program limit.
5. Tenor is exactly 30, 60, or 90 days.
6. `discountFee = round(requestedAmount * 0.06 * tenorDays / 360, 2)`;
   processing fee is 50.00; `netPayout = requestedAmount - discountFee - 50.00`.
7. Beneficiary must match `^BEN-[A-Z]{2}-[0-9]{3}$`, terms must be acknowledged,
   and at least one `INVOICE_COPY` attachment is required.
8. Submission tokens are unique and duplicate submissions return the existing
   request reference without financing invoices twice.

## Endpoints

The shared JSON facade is under `/api/v1`:

- `GET /dashboard`
- `GET /invoices?ref=&status=&currency=`
- `GET /requests`
- `PUT /draft`
- `POST /requests/submit`

Development parity endpoints are under `/__parity`:

- `GET /__parity/state`
- `POST /__parity/reset`

Parity endpoints are disabled when `PARITY_ENV=production`; otherwise they are
enabled by default and can be controlled with `-Dparity.trace=false`.

The JSP workflow is available at `/dashboard`, `/invoices`, `/drawdown`,
`/attachments`, `/review`, and `/requests`. Stable `id` and `data-testid`
selectors are included for browser trace capture.
