# Nurture email drafts (run 8efc13122956)

Source: Offline run: every variant below is a template. No model was called.
Status: PENDING APPROVAL. Copy approved text into HubSpot emails by hand. Nothing is sent by this agent.

## NURTURE_WELCOME (1 contacts)
Audience facts: stages {'lead': 1}, fit {'B': 1}, engagement {'cooling': 1}

### Variant A (source: template)
Subject: Welcome, {{contact.firstname}}: where to start
Preview: Three short reads picked for teams like {{company.name}}

Hi {{contact.firstname}},

Thanks for signing up. Over the next two weeks I'll send three short emails, each one practical thing you can use straight away.

First up: the one-page guide most new teams start with. {{content.primary_guide}}

If none of this is relevant, reply and tell me what you are working on instead.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

### Variant B (source: template)
Subject: {{contact.firstname}}, a quick start guide
Preview: The shortest path to a first result

Hi {{contact.firstname}},

Most people who sign up want one thing first: a working example they can copy. Here it is. {{content.primary_guide}}

Next week I'll share how other teams adapted it.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

## NURTURE_EDUCATION (1 contacts)
Audience facts: stages {'lead': 1}, fit {'A': 1}, engagement {'cooling': 1}

### Variant A (source: template)
Subject: How teams like {{company.name}} handle this
Preview: One example, five minutes to read

Hi {{contact.firstname}},

Here is a short example of how a similar team approached the problem, what they changed first and what they would do differently. {{content.case_study}}

If it's useful, the next email covers the setup in more detail.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

### Variant B (source: template)
Subject: A checklist you can steal
Preview: What to check before you change anything

Hi {{contact.firstname}},

I put together a short checklist we use before changing a process. It takes ten minutes and usually saves a week. {{content.checklist}}

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

## RE_ENGAGE (2 contacts)
Audience facts: stages {'lead': 2}, fit {'B': 1, 'C': 1}, engagement {'dormant': 2}

### Variant A (source: template)
Subject: Still want these emails, {{contact.firstname}}?
Preview: One click to stay, or we'll stop

Hi {{contact.firstname}},

We haven't heard from you in a while, so I want to check these emails are still useful. If they are, click below and nothing changes. {{content.stay_subscribed}}

If we don't hear back, we'll stop sending marketing emails so we're not cluttering your inbox.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

### Variant B (source: template)
Subject: What changed since you last looked
Preview: Three updates in two minutes

Hi {{contact.firstname}},

A lot has changed since you last visited. Here are the three updates people ask about most. {{content.updates}}

Not relevant any more? Use the link below and we'll stop.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

## ONBOARD (1 contacts)
Audience facts: stages {'customer': 1}, fit {'A': 1}, engagement {'cooling': 1}

### Variant A (source: template)
Subject: Your first week: the three settings that matter
Preview: Set these up first

Hi {{contact.firstname}},

Welcome aboard. Teams that get value fastest set up three things in week one. Here they are, with a short guide for each. {{content.onboarding_guide}}

Your account team is copied on this programme, so reply any time.

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

### Variant B (source: template)
Subject: Getting {{company.name}} set up
Preview: A checklist for your first month

Hi {{contact.firstname}},

Here is the checklist we walk every new customer through in their first month. {{content.onboarding_checklist}}

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

## EXPAND (1 contacts)
Audience facts: stages {'customer': 1}, fit {'A': 1}, engagement {'warm': 1}

### Variant A (source: template)
Subject: {{company.name}} is close to its limit
Preview: Options before you hit it

Hi {{contact.firstname}},

Your team is using more than when you started. Here's a short overview of the options, and your account manager can walk you through them. {{content.expansion_overview}}

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

### Variant B (source: template)
Subject: What teams add after the first year
Preview: The features customers turn on next

Hi {{contact.firstname}},

After the first year, most customers turn on one of three things. Here's what they are and who they suit. {{content.feature_overview}}

You are receiving this because of your preferences with us. Unsubscribe: {{unsubscribe_link}}

