# Follow-Up Scheduler for OPTRIXTRADES Telegram Bot

## Overview

The Follow-Up Scheduler is a component of the OPTRIXTRADES Telegram Bot that automatically sends follow-up messages to users who start but don't complete the verification process. This helps increase conversion rates by reminding users to complete their registration and deposit.

## Features

- Automatically schedules a series of 10 follow-up messages over a period of days
- First follow-up is sent 4 hours after initial interaction
- Subsequent follow-ups are sent approximately daily
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

1. **Day 1 (4 hours)**: Reminder of benefits, gentle nudge
2. **Day 2**: Scarcity and social proof
3. **Day 3**: Value recap
4. **Day 4**: Personal outreach and soft CTA
5. **Day 5**: Last chance with exit option
6. **Day 6**: Education and trust-building
7. **Day 7**: Light humor and re-activation
8. **Day 8**: FOMO and success stories
9. **Day 9**: Start small offer
10. **Day 10**: Final reminder and hard close

## Customization

To modify the follow-up sequence:

1. Edit the handler functions in `verification.py`
2. Adjust timing in the `_schedule_follow_up` method in `follow_up_scheduler.py`

## Dependencies

- Python 3.7+
- python-telegram-bot v20+
- asyncio