# T014 MANUAL GATE — Review-minta (feature 009)

Generálva: 2026-10-13 | Artifact: data/raw/tickets_texts.jsonl (v1, batch-size 4, 2057/2057, T013 PASSED)

Kategóriánként 2 zárt + 1 nyitott ticket (véletlen, seed=20261013). Nyitottnál resolution_notes-nak NULL-nak kell lennie.


====================================================================================================
## API Integrations
====================================================================================================

--- Ticket 848724 | API Integrations / Authentication Error | P3 | CLOSED | breached: resp=False res=True | reopened=False | csat=-
  short_description: The API integration returns an authentication error for legacy clients.
  description:       A partner integration is failing with an authentication error. The issue occurs when the legacy client attempts to refresh its token. This is a moderate priority issue affecting data synchronization.
  resolution_notes:  The team discovered that the legacy client was using an outdated token format. The engineer updated the client configuration to use the new format and confirmed successful authentication.

--- Ticket 848372 | API Integrations / Rate Limiting | P4 | CLOSED | breached: resp=False res=True | reopened=False | csat=-
  short_description: The API rate limiter is blocking legitimate requests during peak traffic hours.
  description:       Developers are experiencing intermittent 429 errors when calling the integration API. This issue affects the legacy API gateway and disrupts data synchronization for partner applications. The problem is most noticeable during high-traffic periods when the rate limit thresholds are exceeded.
  resolution_notes:  The rate limit thresholds were set too low for the current traffic volume. The team increased the limits and implemented a sliding window algorithm for more accurate tracking. The API was load-tested to confirm that legitimate requests are no longer blocked.

--- Ticket 849086 | API Integrations / Authentication Error | P4 | OPEN | breached: resp=False res=False | reopened=False | csat=-
  short_description: The API client receives an authentication error when calling the user endpoint.
  description:       A developer reported that the integration with the user management API is failing. The client is receiving an authentication error whenever it attempts to call the user endpoint. This is a minor issue affecting only a single test environment.
  resolution_notes:  NULL

====================================================================================================
## Account Access
====================================================================================================

--- Ticket 848673 | Account Access / 2FA Reset | P3 | CLOSED | breached: resp=False res=False | reopened=False | csat=-
  short_description: The user needs a reset for the two-factor authentication device.
  description:       The reporter lost access to the mobile application used for two-factor authentication. This prevents the user from logging into the legacy portal. The issue is isolated to a single account and does not affect other team members.
  resolution_notes:  The support team verified the user identity through secondary channels. The two-factor authentication device was reset and a new enrollment code was issued. The user confirmed successful login after re-enrolling the new device.

--- Ticket 848016 | Account Access / Password Reset | P3 | CLOSED | breached: resp=False res=False | reopened=False | csat=-
  short_description: A user requested a password reset due to repeated login failures.
  description:       The user reported multiple failed login attempts and requested a password reset to regain access. The account was not locked, but the user was unable to proceed with the self-service reset process. The user needed assistance to restore normal access to their workspace.
  resolution_notes:  The agent confirmed the user's identity and manually triggered a password reset email. The user received the reset link and successfully updated their credentials. The agent verified that the new password worked correctly and the account was fully accessible.

--- Ticket 849149 | Account Access / Password Reset | P2 | OPEN | breached: resp=False res=False | reopened=False | csat=-
  short_description: The user cannot access the portal after a failed password reset attempt.
  description:       A staff member reported that the password reset link expired before they could complete the process. The account is now locked, preventing access to critical business tools. This issue is blocking their ability to start their shift.
  resolution_notes:  NULL

====================================================================================================
## Fulfilment & Logistics
====================================================================================================

--- Ticket 847467 | Fulfilment & Logistics / Tracking Updates | P1 | CLOSED | breached: resp=True res=True | reopened=True | csat=-
  short_description: Critical tracking data is missing for high-value orders across all regions.
  description:       A severe outage is preventing tracking updates for all high-value orders. This is impacting customer trust and operational visibility. The issue started early in the morning and has not been resolved despite initial attempts. The business impact is significant due to the volume of affected transactions.
  resolution_notes:  The team identified a database connection timeout as the root cause of the missing data. They increased the connection pool size and restarted the affected services. The tracking data has been restored and verified for accuracy across all regions.

--- Ticket 848367 | Fulfilment & Logistics / Carrier Sync Failure | P3 | CLOSED | breached: resp=False res=False | reopened=False | csat=-
  short_description: The carrier tracking data fails to sync with the order system.
  description:       The logistics team reported that tracking updates from the carrier were not appearing in the customer portal. The issue affected a batch of orders shipped on the previous day. The delay in information caused support inquiries from customers who could not see their shipment status.
  resolution_notes:  The integration team found that the carrier API endpoint had changed its response format. The engineers updated the parser to handle the new data structure and reprocessed the failed sync jobs. The tracking information for the affected orders was successfully updated in the system.

--- Ticket 849198 | Fulfilment & Logistics / Tracking Updates | P3 | OPEN | breached: resp=False res=False | reopened=False | csat=-
  short_description: The tracking system fails to update the status for recent shipments.
  description:       The logistics team reported that the tracking system is not updating the status for several recent shipments. This delay is causing confusion for customers who are checking their delivery progress. The issue appears to be isolated to a specific batch of orders processed last night.
  resolution_notes:  NULL

====================================================================================================
## Notifications
====================================================================================================

--- Ticket 848887 | Notifications / Webhook Retries | P4 | CLOSED | breached: resp=False res=False | reopened=False | csat=-
  short_description: Webhook retries are failing silently for a specific integration endpoint.
  description:       A partner noticed that webhook notifications are not being delivered to their endpoint. The retry mechanism is not logging errors, making it difficult to diagnose. This is a minor issue affecting only one integration partner.
  resolution_notes:  The team found that the endpoint was returning a non-standard error code. The retry logic was updated to handle this specific code. The partner confirmed that webhooks are now being delivered correctly.

--- Ticket 848689 | Notifications / Template Syntax Error | P3 | CLOSED | breached: resp=True res=True | reopened=False | csat=-
  short_description: The email template fails to render due to a syntax error in the header.
  description:       The marketing team reported that the weekly newsletter template is not rendering correctly. The system logs indicate a syntax error in the header section, which prevents the email from being sent. This issue affects all outgoing notifications for that specific campaign.
  resolution_notes:  The developer identified a missing closing tag in the HTML header. The team corrected the syntax and tested the template with sample data. The fix was verified by successfully sending a test email to the internal group.

--- Ticket 849024 | Notifications / Template Syntax Error | P4 | OPEN | breached: resp=False res=False | reopened=False | csat=-
  short_description: The notification template displays a syntax error in the preview.
  description:       The marketing team noticed a syntax error in the email template preview. The error prevents the template from being saved correctly. The team will review the code to fix the formatting issue.
  resolution_notes:  NULL

====================================================================================================
## Payments & Checkout
====================================================================================================

--- Ticket 848991 | Payments & Checkout / Card Declines | P1 | CLOSED | breached: resp=False res=True | reopened=False | csat=-
  short_description: The payment gateway rejects valid credit card transactions.
  description:       The checkout system is failing to process credit card payments for a significant number of customers. This critical issue is causing immediate revenue loss and customer frustration. The error messages indicate a generic decline code from the payment processor.
  resolution_notes:  The payments team discovered that a recent configuration change had disabled a specific card network. The engineer re-enabled the network and cleared the cached error states. The finance team confirmed that new transactions are processing correctly.

--- Ticket 848870 | Payments & Checkout / Card Declines | P2 | CLOSED | breached: resp=False res=True | reopened=False | csat=-
  short_description: Multiple card declines occurred during the evening peak traffic period.
  description:       Several customers reported failed payment attempts for valid credit cards. The issue affected a significant portion of checkout sessions. The team noted that the problem persisted despite initial troubleshooting.
  resolution_notes:  The root cause was a timeout in the legacy authentication service. The service timeout settings were adjusted to handle higher loads. The team confirmed that payment success rates returned to normal levels.

--- Ticket 849094 | Payments & Checkout / Refund Processing | P3 | OPEN | breached: resp=False res=False | reopened=False | csat=-
  short_description: The refund for order number 12345 has not been processed after five days.
  description:       A customer reported that a refund requested last week has not yet appeared in their account. The transaction was approved on the backend, but the funds have not been returned to the original payment method. The customer is requesting an update on the status of the refund.
  resolution_notes:  NULL
