# Email notifications for PMTiles problems

`Email PMTiles problems` sends an email only when `Generate PMTiles` on `main`
finishes with `failure` or `cancelled`. Successful, skipped, and neutral runs do
not send email. This covers scheduled runs and manual runs, including reruns.
Each failed or cancelled attempt sends its own notification.

The notification is a separate `workflow_run` workflow, so it can run after the
generation job is cancelled by its six-hour time limit. It does not change the
generation schedule or process. The email includes the result and a link to the
specific attempt's logs.

## Setup

1. Enable two-step verification for the Gmail account that will send and receive
   these notifications.
2. Create a dedicated [Google app password](https://myaccount.google.com/apppasswords),
   for example named `openaip-pmtiles alerts`. Use this app password, not your
   normal Google password. See [Google's app password instructions](https://support.google.com/accounts/answer/185833).
3. Open [repository Actions secrets](https://github.com/jobes/openaip-pmtiles/settings/secrets/actions)
   and add these **repository secrets**, using **New repository secret**:

   | Name | Value |
   | --- | --- |
   | `GMAIL_ADDRESS` | Full Gmail address; this is both sender and recipient. |
   | `GMAIL_APP_PASSWORD` | The dedicated Google app password. |

   Store both values as secrets, not plain repository variables or committed files.
4. Merge the notification workflow into `main`. GitHub requires `workflow_run`
   listeners to exist on the default branch. It applies to subsequent completion
   events, not historical runs.
5. Once configured, turn off GitHub's built-in **Actions → Email** notifications
   in [personal notification settings](https://github.com/settings/notifications)
   to avoid duplicate failure emails. The custom workflow sends both failure and
   cancellation alerts, with no success emails. This personal setting affects
   built-in Actions emails across your repositories.

Gmail delivery uses `smtp.gmail.com:465` with certificate-verified TLS and Python's
standard library. No third-party mail action, package, repository checkout, or
GitHub API permission is needed. Credentials are never printed.

## Verification and troubleshooting

After the next failed or cancelled `Generate PMTiles` attempt, open
[Actions](https://github.com/jobes/openaip-pmtiles/actions) and check
`Email PMTiles problems`. Its mail job should succeed and the email should arrive
at `GMAIL_ADDRESS`. A successful generation should leave the mail job skipped.

Delivery cannot be checked until the secrets are configured and an eligible run
completes. If delivery fails, inspect the notification job's log and Gmail's spam
folder. Missing secrets fail with an explicit setup message; authentication or
SMTP errors fail the notification job. The original run's result is unchanged.

If Google does not offer app passwords for the account, consult its instructions
above; organizational policies or Advanced Protection may prevent their use.
Google revokes app passwords when the account password changes, so update the
repository secret after generating a replacement.
