# The plaza: a cast that is about the page

## Problem

All 65 speakers walked the plaza at once as an anonymous clump: no names until someone spoke, no
relation to what the visitor was looking at, nothing to click.

## Design

- **A cast on duty.** At most 12 characters are on stage (5 on a phone), spread over the width and
  larger. The others are off stage and cost nothing. Walking on and off is brisk.
- **About the page.** Results, a talk and a speaker page name their speakers in a hidden
  `data-spotlight` marker. Those speakers (up to 6, fewer on a phone) walk to the front row with their
  name on a blue plate; a talk page also brings the speakers of related talks. Pages without a marker
  (home, Browse) show only the ambient cast. The marker replaces the `HX-Trigger` header, so a full page
  load, a boosted navigation and a live search all work the same way.
- **Interactive.** Each character's tag is a link to their talk (boosted by htmx). Hover or focus turns
  the character to the visitor, waves, and shows the talk title. The front row is keyboard reachable;
  the ambient cast is not, since the results already link the same talks.
- **Conversations stay.** A speaker who is off stage walks on for a conversation and leaves after it;
  the bubble appears when the speaker has walked up to the listener.
- **Reduced motion** still renders one frame, now with the front row in place.

## Out of scope

Changing who talks to whom, the conversation text, the character model.
