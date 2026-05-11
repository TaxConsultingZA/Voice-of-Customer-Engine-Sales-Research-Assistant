#!/usr/bin/env python3
"""
Synthetic SA Customer Corpus Generator
---------------------------------------
Generates 500 labelled customer interaction samples for the VoC Engine
sentiment benchmark (F1 ≥ 0.94 gate).

Distribution: 200 negative · 175 neutral · 125 positive
Focus:        40% Authentication & Onboarding (Signal Alpha)
Language:     English with SA slang, Afrikaans phrases, Zulu/Xhosa openers

Run:    python scripts/generate_corpus.py
Output: tests/fixtures/sa_customer_corpus/sample_001.json … sample_500.json

All samples are synthetic — no real customer PII.
"""

import json
import random
from pathlib import Path

SEED = 42
random.seed(SEED)

OUTPUT_DIR = Path("tests/fixtures/sa_customer_corpus")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# SA linguistic flavour pools
# ─────────────────────────────────────────────────────────────────────────────

NEG_OPENERS = [
    "Eish,", "Ag,", "Yoh,", "Haibo,", "Jislaaik,", "Aikona,",
    "I am very frustrated.", "This is completely unacceptable.",
    "Dis nie reg nie —", "I've had enough.",
    "I cannot believe this.", "Honestly,",
]

POS_OPENERS = [
    "Lekker work!", "Sharp sharp!", "Howzit!", "Yebo!", "Sawubona,",
    "Just wanted to say", "Baie dankie!", "Great news —",
    "Pleased to report", "Happy to share",
]

NEU_OPENERS = [
    "Howzit,", "Hi there,", "Good day,", "Dumela,",
    "Hello,", "Good morning,", "Sanibonani,",
    "I would like to enquire about", "Quick question:",
    "Could you please clarify",
]

NEG_CLOSERS = [
    "This is unacceptable!", "Please sort this out urgently.",
    "I expect a response within 24 hours.", "Very disappointed.",
    "Lank frustrated now.", "This is hectic — please help.",
    "I may have to cancel my subscription.",
    "Ag, I've been waiting too long.", "Eish, please fix this.",
    "This is really kak service.",
]

POS_CLOSERS = [
    "Baie dankie!", "Sharp!", "Keep up the great work!",
    "Very impressed — well done.", "Lekker service!",
    "Appreciate the quick help.", "Five stars from me.",
    "Will definitely recommend.", "Sharp sharp!",
]

NEU_CLOSERS = [
    "Please advise.", "Looking forward to your response.",
    "Kind regards.", "Thanks in advance.",
    "Please let me know.", "Awaiting your feedback.",
]

# Per-language greeting and thanks phrases used for authentic code-switching.
# Customers open/close in their home language; body text stays in English.
LANG_PHRASES = {
    "en": {
        "neg_open": ["I am frustrated,", "This is unacceptable,", "I cannot believe this,"],
        "pos_open": ["Just wanted to say,", "Happy to share,", "Great news —"],
        "neu_open": ["Hello,", "Hi there,", "Good morning,"],
        "neg_close": ["Very disappointed.", "Please fix this urgently.", "I expect better."],
        "pos_close": ["Thank you!", "Much appreciated.", "Well done!"],
        "neu_close": ["Please advise.", "Thank you in advance.", "Looking forward to your reply."],
    },
    "af": {
        "neg_open": ["Dis nie reg nie —", "Ek is baie gefrustreerd,", "Ag, dit is onaanvaarbaar,"],
        "pos_open": ["Baie dankie!", "Groot nuus —", "Ek is bly om te deel,"],
        "neu_open": ["Hoe gaan dit,", "Goeie dag,", "Goeiemôre,"],
        "neg_close": ["Geen probleem nie — dit moet reggemaak word.", "Ek verwag 'n reaksie.", "Baie teleurgesteld."],
        "pos_close": ["Baie dankie!", "Geen probleem!", "Uitstekende diens!"],
        "neu_close": ["Asseblief adviseer.", "Dankie by voorbaat.", "Groete."],
    },
    "zu": {
        "neg_open": ["Sawubona,", "Ngiyakhala —", "Akukholeki lokhu,"],
        "pos_open": ["Sawubona!", "Ngiyajabula ukusho,", "Yebo,"],
        "neu_open": ["Sawubona,", "Sanibonani,", "Ngicela usizo,"],
        "neg_close": ["Ngiyacela nisombulule lokhu.", "Ngiyakhathazeka kakhulu.", "Ngizocela ukubuyisela imali yami."],
        "pos_close": ["Ngiyabonga kakhulu!", "Hambani kahle!", "Niyenza umsebenzi omuhle!"],
        "neu_close": ["Ngiyabonga.", "Ngilindele impendulo yenu.", "Ngicela ningithumele ulwazi."],
    },
    "xh": {
        "neg_open": ["Molo,", "Hayi, akufanelanga —", "Ndingakhathazekile kakhulu,"],
        "pos_open": ["Molo!", "Ndivuya ukuxelela,", "Ndixelela izindaba ezimnandi,"],
        "neu_open": ["Molo,", "Molweni,", "Ndicela uncedo,"],
        "neg_close": ["Ndiyacela niphande ngoku.", "Ndidanile kakhulu.", "Lo mba kufuneka usolulwe."],
        "pos_close": ["Enkosi kakhulu!", "Nicanda umsebenzi omhle!", "Ndiyabulela!"],
        "neu_close": ["Enkosi.", "Ndicela impendulo.", "Ndilindele ukuva kuni."],
    },
    "st": {
        "neg_open": ["Dumela,", "Ke a kgalemela —", "Ha ke kgotsofalehe,"],
        "pos_open": ["Dumela!", "Ke a leboha,", "Ke na le ditaba tse molemo,"],
        "neu_open": ["Dumela,", "Ke kopa thuso,", "Ke na le potso,"],
        "neg_close": ["Ke kopa hore le lokise bothata bona.", "Ke kgathetse haholo.", "E batla ho lokiswa kapele."],
        "pos_close": ["Ke a leboha haholo!", "Mosebetsi o motle!", "Ke leboha thuso ya lona!"],
        "neu_close": ["Ke a leboha.", "Ke lebeletse karabo ya lona.", "Ke kopa le nthuse."],
    },
    "nso": {
        "neg_open": ["Dumela,", "Ga ke kgotsofalego —", "Ke kwišitšwe ke mahloko,"],
        "pos_open": ["Dumela!", "Ke a leboga,", "Ke na le ditaba tše dingwe tše botse,"],
        "neu_open": ["Dumela,", "Ke nyaka thušo,", "Ke na le potšišo,"],
        "neg_close": ["Ke kgopela gore le lokiše bothata bjo.", "Ke nyaka karabelo ka pela.", "Ga go loke."],
        "pos_close": ["Ke a leboga kudu!", "Mošomo o motle!", "Ke leboga thušo ya lena!"],
        "neu_close": ["Ke a leboga.", "Ke lebelela karabelo ya lena.", "Ke kgopela thušo ya lena."],
    },
    "tn": {
        "neg_open": ["Dumela,", "Ga ke itumelele —", "Ke a nyorilwe,"],
        "pos_open": ["Dumela!", "Ke a leboga,", "Ke na le dikgang tse di molemo,"],
        "neu_open": ["Dumela,", "Ke batla thuso,", "Ke na le potso,"],
        "neg_close": ["Ga go siame — ke kopa lo baakanyetse bothata jono.", "Ke nyaka karabo ka bonako.", "Ke kgateletsegile thata."],
        "pos_close": ["Ke a leboga thata!", "Lo dira sentle!", "Ke leboha thuso ya lona!"],
        "neu_close": ["Ke a leboga.", "Ke emetse karabo ya lona.", "Ke kopa thuso ya lona."],
    },
    "ss": {
        "neg_open": ["Sawubona,", "Angikukholwa —", "Ngikhatsatekile,"],
        "pos_open": ["Sawubona!", "Ngiyabonga,", "Nginemibiko lemihle,"],
        "neu_open": ["Sawubona,", "Ngidzinga lusito,", "Nginemibuzo,"],
        "neg_close": ["Ngicela nikhipha lenkinga.", "Ngikhatsateke kakhulu.", "Loku akukufanele."],
        "pos_close": ["Ngiyabonga kakhulu!", "Nisebenta kahle!", "Ngibonga lusito lwenu!"],
        "neu_close": ["Ngiyabonga.", "Ngilindza impendvulo yenu.", "Ngicela nangisita."],
    },
    "ve": {
        "neg_open": ["Ndaa,", "A zwi ngo luga —", "Ndi a tambudzeka,"],
        "pos_open": ["Ndaa!", "Ndo livhuwa,", "Ndi na mafhungo maawanaho,"],
        "neu_open": ["Ndaa,", "Ndi toda thuso,", "Ndi na mbudziso,"],
        "neg_close": ["Ndi humbela uri lu thuse.", "Ndi khathadzekile ngaho.", "Izwi iri a li ngo luga."],
        "pos_close": ["Ndo livhuwa nga maanda!", "Lu shuma zwaavhuya!", "Ndo livhuwa thuso yanu!"],
        "neu_close": ["Ndo livhuwa.", "Ndi lindela mhindulo yanu.", "Ndi humbela thuso yanu."],
    },
    "ts": {
        "neg_open": ["Avuxeni,", "A swi lungi —", "Ndzi khomiwa hi ku khumbiwa,"],
        "pos_open": ["Avuxeni!", "Ndza khensa,", "Ndzi na mahungu lama kahle,"],
        "neu_open": ["Avuxeni,", "Ndza lava nseketelo,", "Ndzi na swivutiso,"],
        "neg_close": ["Ndza lava leswaku mi lulamisela xiphiqo lexi.", "Ndzi dzunisekile ngopfu.", "Leswi a swi lungi."],
        "pos_close": ["Ndza khensa ngopfu!", "Mi endla ntirho lowunene!", "Ndza khensa nseketelo wa n'wina!"],
        "neu_close": ["Ndza khensa.", "Ndzi rindza nhlamulo ya n'wina.", "Ndza lava ku pfuniwa."],
    },
    "nr": {
        "neg_open": ["Lotjhani,", "Akukho lunge —", "Ngiyakhathazeka,"],
        "pos_open": ["Lotjhani!", "Ngiyabonga,", "Nginezindaba ezimnandi,"],
        "neu_open": ["Lotjhani,", "Ngidinga usizo,", "Nginemibuzo,"],
        "neg_close": ["Ngicela nixazulule inkinga le.", "Ngiyaphoxeka kakhulu.", "Lokhu akufaneleki."],
        "pos_close": ["Ngiyabonga kakhulu!", "Nisebenza kuhle!", "Ngiyabonga ngesizo lenu!"],
        "neu_close": ["Ngiyabonga.", "Ngilindele impendulo yenu.", "Ngicela nangisizeni."],
    },
}

INTENSIFIERS = ["lank", "very", "quite", "extremely", "really", "hectic"]

ACCOUNT_TYPES = ["Enterprise", "Professional", "SMB", "Starter", "Team"]
FEATURES = [
    "dashboard", "export feature", "reporting module", "API integration",
    "analytics tab", "user management", "billing portal",
    "notification system", "mobile app", "data import tool",
]

# ─────────────────────────────────────────────────────────────────────────────
# Template pools — each returns a string
# ─────────────────────────────────────────────────────────────────────────────

def _pick(*pools):
    return random.choice(list(pools))


def _int(lo, hi):
    return random.randint(lo, hi)


NEGATIVE_TEMPLATES = [
    # ── Authentication / Login (Signal Alpha) ────────────────────────────────
    lambda: f"I've been trying to log in for the past {_int(1,5)} hours and keep getting an 'invalid credentials' error even though I haven't changed my password.",
    lambda: f"My password reset email never arrives. I've checked my spam folder {_int(3,8)} times. Nothing.",
    lambda: f"The MFA verification code keeps saying it's expired before I can even type it in. Authentication is completely broken.",
    lambda: f"My account has been locked for {_int(1,4)} days and I still cannot get access. I am a paying {_pick(*ACCOUNT_TYPES)} customer.",
    lambda: f"SSO login with my company account stopped working after your update on Friday. Now nobody in our team can log in.",
    lambda: f"The 'Forgot Password' link does nothing when I click it. It just reloads the same page.",
    lambda: f"I reset my password successfully but the new password still doesn't work. This is going in circles.",
    lambda: f"Your login page gives me a blank white screen on Chrome. I've tried three different browsers and it's the same.",
    lambda: f"MFA setup is completely broken. The QR code won't scan and the manual entry code doesn't work either.",
    lambda: f"I've been locked out {_int(2,5)} times today because the system keeps logging me out mid-session.",
    lambda: f"The login button just spins forever and never actually logs me in. I've cleared cache and cookies.",
    lambda: f"Two-factor authentication codes are being sent to an old phone number I no longer use and I can't change it.",
    lambda: f"My account was suspended without any warning or email explaining why. I cannot log in at all.",
    lambda: f"The password requirements keep changing — now it says my {_int(10,14)}-character password is too short.",
    lambda: f"Login works on desktop but completely fails on mobile. The app just crashes on the login screen.",
    # ── Onboarding ──────────────────────────────────────────────────────────
    lambda: f"I cannot complete my registration. The form keeps saying my business email is invalid but it's perfectly fine.",
    lambda: f"I signed up {_int(2,7)} days ago and still haven't received my verification email. I've resent it {_int(3,6)} times.",
    lambda: f"The setup wizard crashes at step {_int(2,4)} every single time. I've tried on {_int(2,3)} different devices.",
    lambda: f"I registered but my account is stuck on 'pending verification' and there's no way to contact anyone.",
    lambda: f"The onboarding video tutorial links are all broken — they all give me a 404 error.",
    # ── Billing ──────────────────────────────────────────────────────────────
    lambda: f"I was charged R{_int(500,5000)} twice this month for the same subscription. I want a refund immediately.",
    lambda: f"My payment keeps failing at checkout even though my card details are correct. I've tried {_int(3,6)} times.",
    lambda: f"I cancelled my subscription {_int(10,30)} days ago and I'm still being billed. This needs to stop.",
    lambda: f"The invoice I received is for the wrong amount — it shows R{_int(1000,8000)} but my plan is R{_int(200,800)}/month.",
    lambda: f"I cannot update my payment method. The save button does nothing on the billing page.",
    # ── Performance ──────────────────────────────────────────────────────────
    lambda: f"The {_pick(*FEATURES)} is {_pick(*INTENSIFIERS)} slow today. Every click takes {_int(15,60)} seconds to respond.",
    lambda: f"Everything times out after {_int(20,60)} seconds. I cannot get anything done. The system is unusable.",
    lambda: f"Your mobile app crashes every time I try to open the {_pick(*FEATURES)}. Happens consistently.",
    lambda: f"API response times have gone from under 1 second to over {_int(10,30)} seconds. Something is badly broken.",
    lambda: f"The {_pick(*FEATURES)} won't load at all during peak hours. I've been waiting {_int(20,45)} minutes.",
    # ── Reporting / Features ─────────────────────────────────────────────────
    lambda: f"My {_pick(*FEATURES)} keeps showing data from {_int(1,3)} months ago instead of today's figures.",
    lambda: f"The CSV export downloads an empty file every single time. I need this data urgently.",
    lambda: f"My scheduled report hasn't run in {_int(3,14)} days. The automation is completely broken.",
    lambda: f"The {_pick(*FEATURES)} is showing incorrect totals — they don't match the underlying transaction data at all.",
    lambda: f"Data I exported yesterday is different from what the {_pick(*FEATURES)} shows today. Completely inconsistent.",
    # ── Support ──────────────────────────────────────────────────────────────
    lambda: f"I've submitted {_int(3,8)} support tickets in the past {_int(1,3)} weeks and not received a single response.",
    lambda: f"Your live chat says agents are available but I've been waiting {_int(30,120)} minutes with no reply.",
    lambda: f"The support agent I spoke to said the issue was escalated but it's now been {_int(5,14)} days and nothing.",
    lambda: f"I was told the bug would be fixed in {_int(1,3)} days. That was {_int(10,21)} days ago.",
    lambda: f"Every time I call support I get transferred to a different department and have to explain the problem from scratch.",
    # ── Integration ──────────────────────────────────────────────────────────
    lambda: f"The API integration we built stopped working after your update. Our entire workflow is now broken.",
    lambda: f"Webhook notifications stopped firing {_int(2,7)} days ago. We're missing critical data in our system.",
    lambda: f"The Zapier integration throws authentication errors every {_int(1,4)} hours and requires manual re-authorisation.",
    lambda: f"Your API rate limits are too low for our volume. We're hitting limits within {_int(5,20)} minutes of opening.",
    lambda: f"The data sync between your platform and our CRM has been broken for {_int(3,10)} days. Records are out of date.",
    # ── SA-flavoured negative ────────────────────────────────────────────────
    lambda: f"Eish, the login is not working nè. I've tried everything. This is really hectic for us.",
    lambda: f"Ag shame, I'm trying to help a client and your system is down again. Dis nie reg nie.",
    lambda: f"Yoh, the app is lank slow today. Everything is timing out. Please sort this out urgently.",
    lambda: f"Haibo, I've been paying for this service for {_int(6,24)} months and this is the third major outage.",
    lambda: f"Jislaaik, I've submitted the same request {_int(4,8)} times and nobody has helped me. Aikona!",
    lambda: f"Dis nie reg nie — I lost {_int(2,5)} hours of work because your autosave feature stopped working.",
    lambda: f"My password reset is broken — eish, I've tried {_int(5,10)} times now. Can someone please help?",
    lambda: f"Howzit, the dashboard is hectic broken this morning. Nothing loads and I have a client meeting in {_int(20,60)} minutes.",
]

POSITIVE_TEMPLATES = [
    # ── Authentication / Login resolved ──────────────────────────────────────
    lambda: f"The login issue I reported has been fixed. Everything works perfectly now. Sharp sharp!",
    lambda: f"Password reset worked flawlessly this time. The email arrived within {_int(1,3)} minutes. Baie dankie!",
    lambda: f"MFA setup was smooth and straightforward. The QR code scanned first try.",
    lambda: f"SSO is working perfectly after the update. My whole team can now log in without any issues.",
    lambda: f"My account access was restored quickly after I contacted support. Very impressed with the response time.",
    # ── Onboarding ──────────────────────────────────────────────────────────
    lambda: f"The onboarding process was really smooth and easy to follow. Got set up in under {_int(10,30)} minutes.",
    lambda: f"The setup wizard is intuitive and clear. I appreciated the helpful tooltips at each step.",
    lambda: f"Verification email arrived immediately and registration was straightforward. Lekker experience!",
    lambda: f"The getting-started guide is excellent. Clear, well-structured, and easy to follow.",
    lambda: f"Onboarding call with your team was very helpful. They walked us through everything patiently.",
    # ── Feature praise ───────────────────────────────────────────────────────
    lambda: f"The new {_pick(*FEATURES)} is a massive improvement over the previous version. Well done!",
    lambda: f"The {_pick(*FEATURES)} update released this week is exactly what we needed. Lekker work!",
    lambda: f"Your API is well-documented and the integration took less than {_int(1,4)} hours to build.",
    lambda: f"The mobile app is smooth and fast. Major improvement from the previous version.",
    lambda: f"The {_pick(*FEATURES)} export now includes all the fields we need. Sharp — great update.",
    lambda: f"Performance has improved significantly since the last release. Pages load in under {_int(1,3)} seconds now.",
    lambda: f"The new dashboard layout is clean and intuitive. Our team picked it up without any training.",
    lambda: f"Really impressed with how stable the system has been this quarter. Zero downtime for us.",
    lambda: f"The automation features have saved our team at least {_int(3,10)} hours per week. Brilliant.",
    lambda: f"The bulk import feature works perfectly. Uploaded {_int(500,5000)} records without a single error.",
    # ── Support ──────────────────────────────────────────────────────────────
    lambda: f"Support resolved my issue within {_int(10,45)} minutes. Outstanding service — thank you!",
    lambda: f"The support agent was patient, knowledgeable, and solved the problem on the first call.",
    lambda: f"Your team went above and beyond to help us during the migration. Baie dankie!",
    lambda: f"Ticket response time was under {_int(1,4)} hours and the solution worked perfectly.",
    lambda: f"I'm genuinely impressed with the level of support. Best experience I've had with any SaaS platform.",
    # ── General positive ─────────────────────────────────────────────────────
    lambda: f"The platform has transformed how our team works. Can't imagine going back to spreadsheets.",
    lambda: f"We've been customers for {_int(1,3)} years and the product keeps getting better. Sharp sharp!",
    lambda: f"The pricing is fair and the value for money is excellent. Lekker service overall.",
    lambda: f"Just renewed our {_pick(*ACCOUNT_TYPES)} plan for another year. Happy customers here!",
    lambda: f"The product roadmap update you shared is really exciting. Looking forward to the new features.",
    # ── SA-flavoured positive ────────────────────────────────────────────────
    lambda: f"Howzit! Just wanted to say the new login flow is lekker smooth. Yebo!",
    lambda: f"Sharp sharp — the issue was fixed faster than expected. Baie dankie to the support team!",
    lambda: f"Sawubona! The platform has been running beautifully this month. Zero complaints from our side.",
    lambda: f"Lekker work on the update! The {_pick(*FEATURES)} is now exactly what we needed.",
    lambda: f"Yoh, the new {_pick(*FEATURES)} is hectic good! Our whole team is impressed.",
    lambda: f"Howzit, just popping in to say your team is sharp. Problem sorted, very happy customer.",
    lambda: f"Baie dankie for the quick fix. The {_pick(*FEATURES)} is working perfectly again. Sharp!",
    lambda: f"Geen probleem with the system today — running like a dream. Lekker!",
]

NEUTRAL_TEMPLATES = [
    # ── Authentication questions ──────────────────────────────────────────────
    lambda: f"How do I reset my password? I can't find the option in the account settings.",
    lambda: f"What browsers are supported for the login page? I want to make sure I'm using a compatible one.",
    lambda: f"Is there a way to set up SSO for our organisation? We use Microsoft Azure AD.",
    lambda: f"How do I enable MFA for my account? I want to improve security.",
    lambda: f"What is the password policy? How often do passwords expire and what are the requirements?",
    lambda: f"Can I log in to the same account from multiple devices simultaneously?",
    lambda: f"How long does a session stay active before it times out automatically?",
    lambda: f"Is there a way to set up biometric login on the mobile app?",
    # ── Onboarding questions ─────────────────────────────────────────────────
    lambda: f"I just signed up for a {_pick(*ACCOUNT_TYPES)} plan. What are the next steps to get started?",
    lambda: f"How long does the verification process usually take after signing up?",
    lambda: f"Is there an onboarding webinar I can join to learn the platform?",
    lambda: f"Where can I find the getting-started documentation for new users?",
    lambda: f"Can I import my existing data during the onboarding process? We have about {_int(500,10000)} records.",
    lambda: f"What training resources are available for new team members joining our account?",
    # ── Billing / Account questions ──────────────────────────────────────────
    lambda: f"I need to update the billing contact on our account. How do I do that?",
    lambda: f"Can you explain the difference between the {_pick(*ACCOUNT_TYPES)} and Professional plans?",
    lambda: f"When does my current billing cycle end? I'd like to know before making any changes.",
    lambda: f"Is there an annual payment option that offers a discount compared to monthly billing?",
    lambda: f"How do I add additional user seats to our existing {_pick(*ACCOUNT_TYPES)} plan?",
    lambda: f"Does the {_pick(*ACCOUNT_TYPES)} plan include API access? If so, what are the rate limits?",
    lambda: f"Can I downgrade my plan mid-cycle? Will I receive a prorated refund?",
    lambda: f"What is the cancellation policy? How much notice do I need to give?",
    # ── Feature / Technical questions ────────────────────────────────────────
    lambda: f"When is the new {_pick(*FEATURES)} feature expected to be released?",
    lambda: f"Is it possible to schedule automated exports from the {_pick(*FEATURES)}?",
    lambda: f"What file formats does the {_pick(*FEATURES)} support for imports?",
    lambda: f"Is there a way to customise the {_pick(*FEATURES)} to show only certain columns?",
    lambda: f"Does your platform integrate with Salesforce or HubSpot?",
    lambda: f"What is the maximum file size for data imports?",
    lambda: f"Is there an audit trail or activity log I can access for compliance purposes?",
    lambda: f"Can I set up role-based access control for different team members?",
    lambda: f"What are the data retention policies for our account data?",
    lambda: f"Is the platform POPIA compliant? We deal with South African customer data.",
    # ── Support / Status questions ───────────────────────────────────────────
    lambda: f"Is there a status page where I can check if there are any ongoing incidents?",
    lambda: f"What are your support hours? I'm in Johannesburg (SAST) and need to know when I can reach someone.",
    lambda: f"I submitted a ticket {_int(2,5)} days ago. Can you provide a status update on the progress?",
    lambda: f"What is the typical response time for {_pick(*ACCOUNT_TYPES)} plan support tickets?",
    lambda: f"Is there a dedicated account manager for {_pick(*ACCOUNT_TYPES)} plan customers?",
    # ── SA-flavoured neutral ─────────────────────────────────────────────────
    lambda: f"Howzit, quick question — how do I change the language settings on my account?",
    lambda: f"Dumela, I'd like to know when the new {_pick(*FEATURES)} feature will be available.",
    lambda: f"Hoe gaan dit? I need some help understanding the pricing for additional users.",
    lambda: f"Sanibonani — could you tell me what data regions are available? We need our data in South Africa.",
    lambda: f"Howzit, just checking — is there scheduled maintenance planned for this weekend?",
    lambda: f"Hi there, I'm based in Cape Town and want to confirm that data stays in the SA region.",
    lambda: f"Can you explain what happens to our data if we cancel our subscription?",
    lambda: f"I'm looking at migrating from a competitor — is there a migration assistance programme?",
    lambda: f"What are the uptime SLAs for the {_pick(*ACCOUNT_TYPES)} plan?",
    lambda: f"Is there a sandbox environment we can use for testing before going live?",
]

# ─────────────────────────────────────────────────────────────────────────────
# Channel and topic metadata
# ─────────────────────────────────────────────────────────────────────────────

CHANNELS = ["email", "chat", "whatsapp", "call", "web_form", "mobile_app", "survey"]
CHANNEL_WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.10, 0.05, 0.05]

TOPIC_MAP = {
    "negative": [
        ("Authentication.Login.PasswordReset", 0.14),
        ("Authentication.Login.AccountLocked", 0.10),
        ("Authentication.Mfa.VerificationFailure", 0.08),
        ("Authentication.Login.SsoFailure", 0.06),
        ("Onboarding.Registration.EmailVerification", 0.08),
        ("Onboarding.Setup.ProfileConfiguration", 0.04),
        ("Billing.Payment.ProcessingError", 0.10),
        ("Billing.Subscription.Cancellation", 0.05),
        ("Reporting.Dashboards.Export", 0.10),
        ("Reporting.Dashboards.Export", 0.05),
        ("Authentication.Login.PasswordReset", 0.10),
        ("Onboarding.Registration.AccountCreation", 0.05),
        ("Billing.Payment.ProcessingError", 0.05),
    ],
    "positive": [
        ("Authentication.Login.PasswordReset", 0.15),
        ("Onboarding.Registration.Setup", 0.20),
        ("Onboarding.Training.Onboarding", 0.10),
        ("Reporting.Dashboards.Export", 0.15),
        ("Authentication.Login.SsoFailure", 0.10),
        ("Billing.Subscription.Cancellation", 0.05),
        ("Onboarding.Registration.EmailVerification", 0.10),
        ("Reporting.Dashboards.Export", 0.15),
    ],
    "neutral": [
        ("Authentication.Login.PasswordReset", 0.12),
        ("Authentication.Mfa.SetupFailure", 0.06),
        ("Onboarding.Registration.AccountCreation", 0.10),
        ("Onboarding.Training.Onboarding", 0.08),
        ("Billing.Payment.ProcessingError", 0.12),
        ("Billing.Subscription.Cancellation", 0.08),
        ("Reporting.Dashboards.Export", 0.10),
        ("Authentication.Login.SsoFailure", 0.06),
        ("Compliance.Popia.DataAccessRequest", 0.08),
        ("Onboarding.Setup.ProfileConfiguration", 0.10),
        ("Authentication.Login.AccountLocked", 0.05),
        ("Billing.Subscription.Cancellation", 0.05),
    ],
}

# All 11 spoken official SA languages.
# Distribution approximates population share in customer-facing digital contexts.
# English dominates business writing; other languages appear via code-switching.
LANGUAGES = {
    "negative": [
        ("en",  0.63), ("af", 0.12), ("zu", 0.08), ("xh", 0.05),
        ("st",  0.04), ("tn", 0.03), ("nso", 0.02), ("ss", 0.01),
        ("ve",  0.01), ("ts", 0.005), ("nr", 0.005),
    ],
    "positive": [
        ("en",  0.60), ("af", 0.14), ("zu", 0.09), ("xh", 0.06),
        ("st",  0.04), ("tn", 0.03), ("nso", 0.02), ("ss", 0.01),
        ("ve",  0.005), ("ts", 0.005), ("nr", 0.00),
    ],
    "neutral": [
        ("en",  0.65), ("af", 0.12), ("zu", 0.07), ("xh", 0.05),
        ("st",  0.04), ("tn", 0.03), ("nso", 0.02), ("ss", 0.01),
        ("ve",  0.005), ("ts", 0.005), ("nr", 0.00),
    ],
}

SA_SLANG_TERMS = [
    "eish", "lekker", "howzit", "yebo", "haibo", "ag", "sharp",
    "hectic", "lank", "baie dankie", "ja nee", "aikona", "jislaaik",
    "dis nie reg nie", "yoh",
]


def _weighted_choice(options):
    items = [o[0] for o in options]
    weights = [o[1] for o in options]
    return random.choices(items, weights=weights, k=1)[0]


def _has_slang(text: str) -> bool:
    return any(term in text.lower() for term in SA_SLANG_TERMS)


def _build_text(label: str, template_fn, language: str = "en") -> str:
    base = template_fn()
    phrases = LANG_PHRASES.get(language, LANG_PHRASES["en"])

    # 35% chance of prepending a language-specific opener
    if label == "negative" and random.random() < 0.35:
        base = random.choice(phrases["neg_open"]) + " " + base
    elif label == "positive" and random.random() < 0.35:
        base = random.choice(phrases["pos_open"]) + " " + base
    elif label == "neutral" and random.random() < 0.25:
        base = random.choice(phrases["neu_open"]) + " " + base

    # 40% chance of appending a language-specific closer
    if label == "negative" and random.random() < 0.40:
        base = base.rstrip(".") + ". " + random.choice(phrases["neg_close"])
    elif label == "positive" and random.random() < 0.40:
        base = base.rstrip(".") + ". " + random.choice(phrases["pos_close"])
    elif label == "neutral" and random.random() < 0.30:
        base = base.rstrip(".") + ". " + random.choice(phrases["neu_close"])

    return base


# ─────────────────────────────────────────────────────────────────────────────
# Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_samples():
    plan = (
        [("negative", NEGATIVE_TEMPLATES)] * 200
        + [("neutral", NEUTRAL_TEMPLATES)] * 175
        + [("positive", POSITIVE_TEMPLATES)] * 125
    )
    random.shuffle(plan)

    samples = []
    for i, (label, pool) in enumerate(plan, start=1):
        template_fn = random.choice(pool)
        language = _weighted_choice(LANGUAGES[label])
        text = _build_text(label, template_fn, language)
        topic_options = TOPIC_MAP[label]
        taxonomy_path = _weighted_choice(topic_options)
        channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]

        sample = {
            "id": f"sample_{i:03d}",
            "text": text,
            "label": label,
            "channel": channel,
            "taxonomy_path": taxonomy_path,
            "language": language,
            "contains_slang": _has_slang(text),
            "annotator": "synthetic",
        }
        samples.append(sample)

    return samples


def main():
    samples = generate_samples()

    counts = {"negative": 0, "positive": 0, "neutral": 0}
    lang_counts: dict = {}
    slang_count = 0

    for sample in samples:
        path = OUTPUT_DIR / f"{sample['id']}.json"
        path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
        counts[sample["label"]] += 1
        lang_counts[sample["language"]] = lang_counts.get(sample["language"], 0) + 1
        if sample["contains_slang"]:
            slang_count += 1

    lang_names = {
        "en": "English", "af": "Afrikaans", "zu": "isiZulu", "xh": "isiXhosa",
        "st": "Sesotho", "nso": "Sepedi", "tn": "Setswana", "ss": "siSwati",
        "ve": "Tshivenda", "ts": "Xitsonga", "nr": "isiNdebele",
    }

    print("=" * 52)
    print("SA Customer Corpus -- Generation Complete")
    print("=" * 52)
    print(f"Total samples  : {len(samples)}")
    print(f"  Negative     : {counts['negative']}")
    print(f"  Neutral      : {counts['neutral']}")
    print(f"  Positive     : {counts['positive']}")
    print(f"Contains slang : {slang_count} ({slang_count / len(samples) * 100:.0f}%)")
    print(f"Output dir     : {OUTPUT_DIR.resolve()}")
    print()
    print("Language breakdown:")
    for code, n in sorted(lang_counts.items(), key=lambda x: -x[1]):
        name = lang_names.get(code, code)
        bar = "#" * (n // 5)
        print(f"  {code:4s} {name:<12} {n:3d}  {bar}")
    print("=" * 52)

    # Print one sample per language for spot-check
    shown: set = set()
    print("\nSpot-check (one sample per language):")
    for s in samples:
        lang = s["language"]
        if lang not in shown:
            shown.add(lang)
            print(f"  [{lang}] {s['text'][:110]}")


if __name__ == "__main__":
    main()
