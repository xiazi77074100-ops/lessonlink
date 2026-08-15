# LessonLink UI/UX Product Design

## 1. Product principle

LessonLink is a dual-surface B2B2C SaaS:

- Organization staff use a responsive Admin Web for management and bulk operations.
- Parents complete onboarding, attendance answers, and notifications inside LINE LIFF.
- Frequent actions must work well on phones; configuration-heavy work remains optimized for PC/tablet.
- Every workflow must expose current state, the next action, and a recoverable error path.

The MVP uses one shared LessonLink LINE Official Account. Per-organization LINE channels are not
supported until real customers demonstrate a branding or ownership requirement.

## 2. Organization experience

### 2.1 Information architecture

1. Home
2. Events
3. Children and parents
4. Invitations
5. Organization settings

Desktop uses persistent navigation and data-dense lists. Mobile uses compact navigation, cards,
and full-width primary actions. Staff do not need a separate LIFF application in Phase 13.

### 2.2 Home dashboard

The first screen answers "what needs attention now?":

- Today's and upcoming events
- Attendance counts for each event
- Number of parents who have not answered
- Children without a linked parent
- Failed LINE deliveries
- Direct actions: view attendance, remind unanswered parents, invite a parent

### 2.3 Invitation UX

The primary action is `LINEで招待する`. Secondary actions are copy URL, display QR, and print QR.

Two invitation types are retained:

- Child invitation: one child, one use, short expiry. This is the default from a child detail.
- Organization invitation: multiple uses. This is for initial rollout or sharing in an existing
  organization-wide parent group.

The LINE share message includes organization name, a short explanation, and a single registration
button. Staff explicitly select the friend or group; LessonLink does not infer a private recipient.

### 2.4 Notification UX

For linked parents, staff send directly from an event. The result reports sent, failed, and unlinked
counts. Reminders target only unanswered parents and remain grouped per parent.

Group-bot automation is deferred. Phase 13 shares to groups through the staff member's LINE client.
Bot group binding requires webhook signature validation, tenant-safe group mapping, leave handling,
and privacy rules, and is reconsidered after real usage.

## 3. Parent experience

### 3.1 Onboarding

Onboarding is a short wizard with visible progress:

1. Confirm organization/invitation
2. Confirm child and birth date
3. Completion

A child-specific invitation preselects and hides the child selector. An organization invitation
retains child selection plus birth-date verification. Errors explain how to recover and when to
contact the organization.

### 3.2 Attendance home

- Upcoming events are ordered by start time.
- Child name is always adjacent to its answer controls.
- Buttons are large enough for one-handed use.
- Current answer is visually persistent.
- Saving, success, failure, cancelled-event, and empty states are explicit.
- A failed save never replaces the last confirmed answer.
- No parent password is introduced.

## 4. Phase acceptance criteria

### Phase 13 — Invitation and onboarding UX

- Admin can share an invitation through LINE with one primary action.
- Admin can still copy the URL or show the QR.
- Child-specific, single-use, expiring invitations are supported.
- Parent onboarding shows organization, progress, and completion states.
- The invitation path is usable on a 375 px-wide screen.
- Invite validation and child binding remain tenant-safe and auditable.

### Phase 14 — Daily operations UX

- Admin home shows upcoming events and actionable exceptions.
- Event notification reports sent, failed, and unlinked counts.
- Admin navigation works on desktop and phone without horizontal overflow.
- Parent event cards clearly cover loading, empty, saving, success, error, and cancelled states.

### Phase 15 — Evidence-driven follow-up

Only after production feedback: LINE group bot binding, course/class modeling, advanced staff roles,
and a dedicated staff LIFF quick-action surface.
