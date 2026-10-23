# Pre-launch test report: Vibe Shop (demo app)

Tested: 23 October 2026 · Environment: local (http://127.0.0.1:8899) · Devices: desktop + mobile
Tested by: AI agent using the vibe-app-tester skill

## Verdict

**Not ready: a core journey is broken.**

Visitors can browse the site, but signup accepts empty and invalid details, can create duplicate accounts with a double click, and breaks completely with a long email. The pricing page crashes and shows "NaN" instead of the price, and on phones every page appears as a tiny zoomed-out desktop page.

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 3 |
| Medium | 5 |
| Low | 3 |

## Fix these first

1. F-01 Signup accepts empty and invalid details
2. F-02 Signup breaks with long input and shows nothing to the user
3. F-03 Pricing page crashes and shows "NaN" / "undefined" instead of the price
4. F-04 Double-clicking "Sign up" creates two accounts
5. F-05 Site is not mobile-friendly

## Findings

### F-01 · High · Signup accepts empty and invalid details

**Where:** /signup (both)

**What happens:** Clicking "Sign up" with both fields empty, or with "not-an-email" and a one-character password, is sent to the server and accepted. The page then says "Welcome" with no email. Junk accounts will fill the database and real users get no help when they mistype.

**Steps to reproduce:**
1. Open /signup
2. Leave both fields empty and click "Sign up"

**Expected:** A message under each field ("Enter your email", "Password must be at least 8 characters") and nothing sent.
**Actual:** Request sent, server responds 200, page shows "Welcome".
**Evidence:** qa-results/screens/form_signup_0_empty.png, form_signup_0_invalid.png

**Fix prompt:**
```
The signup form on /signup has no validation on the client or the server. Add validation:
email must be a valid address (max 254 chars), password at least 8 characters. Show the error
message under the relevant field and don't send the request until it's valid. Also validate
the same rules in the POST /api/signup handler and return 400 with a message if they fail.
Verify: submitting empty fields shows two error messages and no network request is made.
```

### F-02 · High · Signup breaks with long input and shows nothing to the user

**Where:** /signup (both)

**What happens:** With a very long email the server returns an error (HTTP 500). The page then crashes in the background ("Unexpected token 'b', "boom" is not valid JSON") and the user sees nothing at all, so they'll assume the site is broken.

**Steps to reproduce:**
1. Open /signup
2. Enter an email longer than 200 characters and any password, click "Sign up"

**Expected:** A clear message such as "This email is too long".
**Actual:** Server error, JavaScript crash, no message shown.
**Evidence:** qa-results/screens/form_signup_0_long.png, form_findings.json (case "long")

**Fix prompt:**
```
In the signup page, go() calls response.json() without checking response.ok, so any server
error crashes the page. Check response.ok first and show a friendly error message in #msg if
the request fails. Separately, POST /api/signup returns 500 for emails over ~200 characters:
validate the length and return 400 with a message instead. Verify: a 300-character email shows
an error message and there are no console errors.
```

### F-03 · High · Pricing page crashes and shows "NaN" and "undefined"

**Where:** /pricing (both)

**What happens:** The price reads "€NaN per month for undefined users". A JavaScript error ("Cannot read properties of undefined (reading 'plan')") also stops the page's script. Visitors deciding whether to pay see a broken price.

**Steps to reproduce:**
1. Open /pricing

**Expected:** "Pro plan: €X per month" with the real numbers.
**Actual:** "€NaN per month for undefined users", plus a JavaScript error.
**Evidence:** qa-results/screens/pricing_desktop.png, pricing_mobile.png

**Fix prompt:**
```
On /pricing, the price is calculated from an undefined value (shows NaN) and the script reads
window.user.plan.name when window.user doesn't exist, which throws. Use the real plan price from
the pricing config, show "Free"/"Contact us" if it's missing, and guard the user lookup
(only read the plan if a user is logged in). Remove the hard-coded "undefined users" text.
Verify: /pricing shows a real price and the console has no errors, logged in and logged out.
```

### F-04 · Medium · Double-clicking "Sign up" creates two accounts

**Where:** /signup (both)

**What happens:** Two quick clicks send two signup requests. On slow connections users often click twice, creating duplicate accounts (or duplicate orders/charges on payment buttons).

**Expected:** The button is disabled with a "Signing up…" state until the response arrives.
**Actual:** Two requests sent, both accepted.

**Fix prompt:**
```
Disable the "Sign up" button and show a loading label while the signup request is in flight,
re-enabling it only if the request fails. Apply the same pattern to every button that saves
or pays. Verify: double-clicking sends only one request.
```

### F-05 · Medium · Site is not mobile-friendly

**Where:** /, /pricing, /signup, /about (mobile)

**What happens:** These pages have no mobile viewport tag, so phones show a tiny zoomed-out desktop page that users must pinch to read. Separately, the table on /menu is 318px wider than a phone screen, forcing sideways scrolling.

**Fix prompt:**
```
Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the shared page
head so it applies to every page. On /menu, make the table fit small screens (allow it to
scroll inside its own container with overflow-x: auto, or stack rows on mobile).
Verify on a 390px-wide screen: no sideways scrolling and text readable without zooming.
```

### F-06 · Medium · "About" link leads to a 404 page

**Where:** / → About (both)

**What happens:** The About link in the header opens "Not found".

**Fix prompt:**
```
The header links to /about but no /about page exists. Either create the About page or remove
the link. Also add a friendly custom 404 page with a link back home.
```

### F-07 · Medium · Home page logs "Failed to fetch user profile"

**Where:** / (both)

**What happens:** Every visit logs an error that the user profile couldn't be loaded. It's invisible to visitors, but usually means a feature (like showing the logged-in user) silently isn't working.

**Fix prompt:**
```
The home page logs "Failed to fetch user profile" on every load, including for logged-out
visitors. Only request the profile when a user is logged in, and handle failures by showing
the logged-out header instead of logging an error.
```

### F-08 · Low · Hero image missing, "Careers" link goes nowhere, signup page has no title

**Where:** / and /signup

**What happens:** The hero image (/missing.png) doesn't load, the "Careers" link points to "#", and the signup page shows no title in the browser tab.

**Fix prompt:**
```
On the home page, replace the broken hero image /missing.png with a real image, and either
create a Careers page or remove the "Careers" link. Add <title>Sign up – Vibe Shop</title>
to the signup page.
```

## What was tested

- Pages crawled: 5 (desktop and mobile)
- Forms tested: 1 (signup) with empty, invalid, long, non-English and double-submit inputs
- Journey tests: not run in this demo (the app has no persistent accounts)
- Manual checks: verified each high finding by reproducing it
- Not tested: payments, email delivery, security

## Re-running the tests

```
python scripts/smoke_crawl.py http://127.0.0.1:8899 --out qa-results
python scripts/form_probe.py http://127.0.0.1:8899/signup --out qa-results --allow-submit
```

---
Severity guide: **Critical** = data loss, money, users seeing others' data, or the main journey is impossible. **High** = a core feature is broken or crashes for many users. **Medium** = works but confusing, wrong or broken for some users/devices. **Low** = polish.
This is functional testing, not a security audit.
