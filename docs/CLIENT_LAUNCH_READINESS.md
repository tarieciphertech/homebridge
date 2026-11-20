# HomeBridge Client Launch Readiness

**Status:** Not yet approved for client onboarding  
**Environment:** Oracle development/test deployment at https://homebridge.cyphertech.co.zw  
**Production domain:** https://homebridge.co.zw (do not assume production deployment is active)  
**Product scope:** Zimbabwe-first student accommodation marketplace

This checklist is the single launch-readiness register. A feature is not considered ready merely because its route or screen exists. Each item must be implemented, tested with the correct account roles, and evidenced before client launch.

## Launch principles

- Keep development/test and production environments separate.
- Do not migrate, rebuild, restart, or reconfigure shared Oracle services without checking impact on every hosted application.
- Back up the HomeBridge database and uploaded files before any production migration or deployment.
- Never commit credentials, private keys, tokens, production environment files, or customer documents.
- Do not publish a property as verified until an administrator has completed the verification process.
- Keep platform service fees separate from rent owed to landlords. Do not combine currencies in financial reporting.
- A HomeBridge tenancy record is not, by itself, a signed lease, proof of rent payment, or confirmation that rent was collected.
- No real client data should be used for destructive tests.

## 1. Product and client journey

- [ ] Public landing page explains the service, coverage, fees, and how HomeBridge works.
- [ ] Student registration, login, logout, password recovery, and account status work.
- [ ] Landlord registration, login, approval, logout, and account status work.
- [ ] Student can search and filter published accommodation by location, property type, budget, availability, institution/campus, and rent period where supported.
- [ ] Property detail pages show accurate rent currency/period, availability, amenities, rules, location, and consented photographs.
- [ ] Student can submit an application, see its status, and withdraw when permitted.
- [ ] Landlord can review applications and propose a viewing.
- [ ] Student can confirm or decline a proposed viewing.
- [ ] Landlord can make a tenancy offer only after the required application and viewing conditions are met.
- [ ] Student can review and accept or decline the offer.
- [ ] Duplicate applications, offers, and tenancy creation are prevented.
- [ ] Student and landlord dashboards show consistent application, viewing, and tenancy states.
- [ ] Empty states, validation errors, mobile layouts, and help/contact paths are clear.

## 2. Landlord and property trust

- [ ] Landlord identity and contact details are reviewed under a documented verification process.
- [ ] Property ownership/authority to advertise is checked and recorded.
- [ ] Property address/location and availability are checked before publication.
- [ ] Listing images are supplied with permission and do not misrepresent the property.
- [ ] Admin can approve, reject, return for correction, publish, unpublish, and feature listings.
- [ ] Verification status and reasons are visible to the appropriate account only.
- [ ] Duplicate, misleading, unavailable, or suspicious listings can be reported and handled.
- [ ] A process exists for periodic re-confirmation of listing availability.

## 3. Fees, rent, and payment records

- [ ] Student service-fee rules, amount, currency, due point, refund policy, and recipient are documented.
- [ ] Landlord listing-fee rules, amount, currency, due point, refund policy, and recipient are documented.
- [ ] Fees are configurable and shown before a user commits.
- [ ] Payment instructions and accepted payment channels are accurate for the launch market.
- [ ] Payment reference and proof submission are validated.
- [ ] Payment proof is private and accessible only to authorized reviewers and its owner as appropriate.
- [ ] Admin can confirm or reject a pending platform-fee payment with an auditable outcome.
- [ ] Account approval and payment confirmation remain separate decisions.
- [ ] Student/landlord payment history shows the correct status and currency.
- [ ] Platform fees and landlord rent are stored and reported as separate financial flows.
- [ ] Rent payment submission/review, if offered in the pilot, is tested separately from HomeBridge service fees.
- [ ] Refunds, mistaken payments, duplicate references, and disputed payments have a documented support process.
- [ ] No payment is described as received until it is actually reconciled.

## 4. Tenancy and agreement lifecycle

- [ ] Tenancy offer validation covers amount, currency, period, room, start/end dates, and terms.
- [ ] Expired, withdrawn, declined, duplicate, and conflicting offers behave correctly.
- [ ] Both parties can see the accepted terms and tenancy status.
- [ ] Agreement review, acknowledgement, signed-copy upload, and download are tested if included in the pilot.
- [ ] Signed documents are stored privately, with role- and record-level authorization.
- [ ] Document retention, deletion, dispute, and access procedures are documented.
- [ ] Agreement wording is reviewed for the applicable Zimbabwean legal context before it is represented as a binding lease.
- [ ] The UI clearly distinguishes an in-platform tenancy record from a signed rental agreement and from rent payment.

## 5. Security and privacy

- [ ] Production uses unique, strong secret values; the application must not silently fall back to development secrets or default administrator credentials.
- [ ] Administrator accounts are provisioned securely, with strong unique passwords and recovery controls.
- [ ] Password policy, reset flow, session handling, and logout behavior are tested.
- [ ] Every student, landlord, and admin route enforces both authentication and correct role.
- [ ] Record-level authorization prevents users from viewing or changing another user's applications, tenancies, payments, maintenance requests, or documents.
- [ ] Private payment proofs, signed agreements, and personal documents are not exposed through public upload paths.
- [ ] Uploads validate file type, size, extension, content, and safe storage location; executable content is rejected.
- [ ] Forms and state-changing routes have CSRF protection.
- [ ] Input validation, output escaping, SQL safety, and error handling are reviewed.
- [ ] Sensitive data is minimized in logs and notifications.
- [ ] HTTPS, secure cookies, security headers, and appropriate session settings are configured for production.
- [ ] Admin actions and important payment/listing/agreement state changes are auditable.
- [ ] Privacy notice, data handling purpose, retention, and user support process are published.

## 6. Application, database, and deployment

- [ ] Production configuration is explicit and fails closed when required settings are missing.
- [ ] Development, staging, and production databases are separate.
- [ ] A managed migration workflow is established; application startup does not act as the production schema migration process.
- [ ] Migrations are tested against a fresh database and a copy of the current development schema.
- [ ] Database constraints and indexes support critical uniqueness and ownership rules.
- [ ] Database and uploaded-file backups are automated, retained, and protected.
- [ ] A restore test has been completed and recorded.
- [ ] Deployment is repeatable and has a documented rollback procedure.
- [ ] Health checks cover application readiness and database connectivity.
- [ ] Logs, disk use, database capacity, certificate renewal, and service availability are monitored.
- [ ] Upload storage persists across container rebuilds and is included in backup/restore.
- [ ] Shared Oracle resources (Docker, Nginx, PostgreSQL, firewall, disk, and ports) are changed only after impact review.
- [ ] Production domain, DNS, TLS, email sender, and external payment instructions are verified before launch.

## 7. Notifications and customer support

- [ ] Email configuration is tested end-to-end with real delivery and bounce handling.
- [ ] Notifications for registration, approval, applications, viewing proposals, tenancy offers, payment decisions, and maintenance updates are accurate.
- [ ] Notifications do not disclose private information to the wrong recipient.
- [ ] Contact/support email and phone are monitored.
- [ ] Support procedures exist for login problems, inaccurate listings, viewing disputes, payment disputes, refunds, safety concerns, and account closure.
- [ ] Response expectations and escalation ownership are documented.

## 8. Test and acceptance evidence

- [ ] Automated tests cover models, routes, validation, and critical business rules.
- [ ] Role-isolation tests cover student-to-student, landlord-to-landlord, and cross-role access.
- [ ] Payment tests cover pending, confirmed, rejected, duplicate, missing-proof, and wrong-owner cases.
- [ ] Upload tests cover permitted files, oversized files, invalid types, private access, and unauthorized access.
- [ ] Agreement and tenancy tests cover full lifecycle and invalid transitions.
- [ ] Migration tests and backup/restore tests pass.
- [ ] Regression tests cover the full student and landlord journeys.
- [ ] Mobile browser testing is completed on common Android screen sizes.
- [ ] A controlled user-acceptance test is completed with separate student, landlord, and admin test accounts.
- [ ] All critical/high-severity defects are resolved or explicitly accepted with a documented mitigation.
- [ ] Test results, tested commit, environment, and tester are recorded.

## 9. Pilot launch decision

Do not onboard real clients until all mandatory security, privacy, payment, backup/restore, role-isolation, and core-journey checks pass.

Before pilot approval, record:

- [ ] Pilot geography and initial institution/campus coverage.
- [ ] Pilot capacity and who is eligible to participate.
- [ ] Named operational owner and support contact.
- [ ] Approved fee schedule and refund/dispute process.
- [ ] Verified initial landlord/property inventory.
- [ ] Final production URL and deployment commit.
- [ ] Backup and rollback confirmation.
- [ ] UAT sign-off and known limitations.
- [ ] Explicit go/no-go decision.

## Current known implementation notes

These are review findings, not launch approvals:

- The tenancy offer and acceptance flow was previously deployed and browser-checked in the Oracle development environment.
- The current `main` branch includes a development configuration fallback secret and startup-time default administrator creation; production behavior must be hardened and verified.
- The application currently calls `db.create_all()` during startup. A managed migration process is required before production.
- Payment proof and other uploaded files need a complete private-storage and authorization review.
- The agreement lifecycle, private signed-copy storage, notifications, rent-payment workflow, and maintenance workflow are represented in an unmerged pull request. They must be reviewed, tested, and integrated deliberately; an open PR is not a deployed feature.
- The README describes planned production routes and capabilities as well as verified development behavior. Verify each route and feature in the target environment before advertising it.

## Recommended execution order

1. Freeze feature expansion temporarily and establish a reproducible test baseline.
2. Review and harden configuration, administrator provisioning, authorization, uploads, and private documents.
3. Review the unmerged agreement/rent/maintenance/notification work and split fixes from unfinished scope if necessary.
4. Add automated unit, integration, and role-isolation tests.
5. Establish database migrations, backup/restore, deployment, and rollback procedures.
6. Complete end-to-end student, landlord, and admin UAT.
7. Prepare client-facing content, policies, verified inventory, fees, and support.
8. Deploy to a separate production environment and run a final go/no-go review.

**Do not mark this document complete by checking boxes based only on code presence. Attach test evidence or a deployment reference for each critical item.**
