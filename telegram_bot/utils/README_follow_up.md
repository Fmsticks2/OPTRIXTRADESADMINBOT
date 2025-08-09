# Follow-Up Scheduler for OPTRIXTRADES Telegram Bot

## Overview

The Follow-Up Scheduler is a component of the OPTRIXTRADES Telegram Bot that automatically sends follow-up messages to users who start but don't complete the verification process. This helps increase conversion rates by reminding users to complete their registration and deposit.

## Features

- Automatically schedules a series of 24 follow-up messages over a period of days
- Follow-ups are sent at random intervals between 7.5-8 hours
- Each message is automatically sent if user hasn't completed verification
- Each follow-up has a unique message and call-to-action
- Messages use different psychological triggers (scarcity, social proof, FOMO, etc.)
- Follow-ups are automatically cancelled when a user completes verification
- Users can opt out of follow-ups by clicking "Not Interested" or "Remove Me From This List"

## Implementation

The scheduler is implemented as a singleton class that is initialized when the bot starts. It uses asyncio tasks to schedule the follow-up messages.

### Key Components

1. `FollowUpScheduler` class - Main scheduler that manages follow-up tasks
2. `init_follow_up_scheduler()` - Initializes the scheduler singleton
3. `get_follow_up_scheduler()` - Gets the scheduler instance
4. Follow-up handler functions in `verification.py` - Define the content of each follow-up message

### Usage

The scheduler is automatically used when:

1. A user starts the verification process (follow-ups are scheduled)
2. A user completes verification (follow-ups are cancelled)
3. A user opts out (follow-ups are cancelled)

## Follow-Up Sequence

The system now includes 24 follow-up sequences, each sent at random intervals between 7.5-8 hours:

1. **Sequence 1 (7.5-8 hours)**: Reminder of benefits, gentle nudge
2. **Sequence 2 (7.5-8 hours later)**: Scarcity and social proof
3. **Sequence 3 (7.5-8 hours later)**: Value recap
4. **Sequence 4 (7.5-8 hours later)**: Personal outreach and soft CTA
5. **Sequence 5 (7.5-8 hours later)**: Last chance with exit option
6. **Sequence 6 (7.5-8 hours later)**: Education and trust-building
7. **Sequence 7 (7.5-8 hours later)**: Light humor and re-activation
8. **Sequence 8 (7.5-8 hours later)**: FOMO and success stories
9. **Sequence 9 (7.5-8 hours later)**: Start small offer
10. **Sequence 10 (7.5-8 hours later)**: Final reminder and hard close
11-24. **Additional sequences**: Extended follow-up campaign with varied messaging

**Note**: Each interval is randomized between 7.5-8 hours to appear more natural and avoid detection as automated messaging.

## Customization

To modify the follow-up sequence:

1. Edit the handler functions in `verification.py`
2. Adjust timing in the `_schedule_follow_up` method in `follow_up_scheduler.py`

## Dependencies

- Python 3.7+
- python-telegram-bot v20+
- asyncio