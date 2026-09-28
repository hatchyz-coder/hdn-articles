---
title: "Why Does Using AI Feel So Draining? The Hidden Work of Checking, Waiting and Worry"
socialTitle: "We delegated work to AI. Why are we managing it instead?"
description: "AI promises faster work, yet users report repeated instructions, verification, unnecessary approval stops and lost focus. Firsthand accounts from Japan and abroad, alongside developer research, reveal the hidden work AI can return to people."
publishedAt: 2026-09-29
category: "World Frictions"
tags:
  - "generative AI"
  - "AI development"
  - "coding agents"
  - "work"
  - "productivity"
  - "developer experience"
author: "Tsuyoshi Hadano"
draft: true
featured: true
sourceUrl: "https://zenn.dev/shingoirie/articles/210b4f6d73ec6c"
cta: editorial
audiences:
  - "general"
section: "world-frictions"
industry: "other"
series: "world-frictions"
contentType: "news-analysis"
---

AI is supposed to make work faster. Hand off the tedious tasks, the promise goes, and people can focus on judgment and creativity. Generative AI and coding agents entered the workplace with that expectation.

But after using them for a while, a different feeling can set in: the work appears to be moving, yet somehow you are more tired. You repeat instructions, wait for replies, check the output, correct the gaps, and figure out why the task stopped. You use AI, but it can feel as though you have more work than before.

I have felt that friction in my own development work with AI. I repeat a direction that has already been given. I am asked again to confirm work that was already agreed. Instead of moving forward, the task gets held up by extra checkpoints. On top of the work itself, I am supervising the AI’s process, tracking progress, and explaining the same thing again.

The question is not only whether AI makes mistakes. Who absorbs the extra checking, waiting and worry that come with using it? And if that time is included, can we still call it efficiency?

## Is “faster, but more tired” just an individual feeling?

A Japanese developer writing on Zenn described using Claude Code and Codex CLI to produce research and fixes faster, while the bottleneck moved from implementation to management: keeping track of active work, noticing when it stops, checking the result, and deciding what to do next. When several AI tasks run at once, someone still has to follow which ones are complete, stalled or waiting for review. Less time writing code does not automatically mean less time managing the work.

Another Japanese developer wrote about using AI to build an internal system. Implementation speed clearly increased, but reviewing the AI-generated code was painful. When an AI helpfully changes surrounding areas as well as the requested part, the diff grows. Review starts to resemble an investigation into what happened, rather than a quick check. The history may be clear to the person who worked with the AI, but not to colleagues who later review the changes. The strain is passed along.

A Qiita post by a developer who uses coding agents at work and on side projects described cases where, after three or four rounds of corrections and waiting for regenerated code, writing it manually would have been faster. The author also recounted spending more than 30 minutes in a loop on a problem that might have taken five minutes to check directly, because the cause was outside the code—in the environment or an external service. These are one practitioner’s experiences, not statistics about all developers. But they capture an important distinction: the time an AI spends working is not the same as the time it takes for the user’s work to be done.

Similar frustrations appear on Reddit. One ChatGPT user wrote that even after giving a clear instruction and explicitly asking the system to act, it would restate the request and ask whether it should proceed. For small changes, the user said, each extra confirmation created another message and another wait. The post explicitly accepts that checks make sense for risky or unclear tasks; the frustration was about routine work being stopped as well.

A Cursor user described an agent that confidently repeated a mistaken diagnosis, changed code, undid its own changes and tried again. After spending days trying to control the tool, the user switched from automatic execution to asking it to explain its reasoning. This is an individual forum post, not a product-wide quality assessment. Still, it shows the distance users sometimes have to bridge between a plausible progress report and an actually solved problem.

These accounts point to more than “AI is hard to use.” Delegating work to AI can create a new supervisory role for the user: instruct, wait, inspect, correct and restart. That work is hard to see as a deliverable, and it is often missing from the headline productivity figures.

## Research finds a gap between productivity and the experience of work

Research on developer experience has also documented this gap.

A 2026 longitudinal study of professional software developers surveyed participants six months apart, including a matched cohort of 95 people. Eighty-two percent of respondents said AI reduced the time they spent writing code, and perceptions of productivity remained positive. At the same time, the share of the matched cohort reporting a worse developer experience in at least one dimension—including flow or cognitive load—nearly doubled, from 14% to 27%. The researchers describe a shift from creating code toward “supervisory engineering work”: directing, evaluating and correcting AI output.

Those figures describe the study’s participants, not every developer around the world. And the reduction in coding time is real for many of them. The point is that shorter task time and a better experience of work do not always move together. People may feel more productive while also losing focus and carrying a heavier verification load.

In Stack Overflow’s 2025 developer survey, 46% of respondents said they distrusted the accuracy of AI output, compared with 33% who trusted it. About 33,000 people answered that survey question. This suggests that many developers use AI without accepting its output at face value. The survey asked about trust, however; it did not directly measure how many minutes verification takes or how much stress it creates.

A 2025 METR experiment reported that experienced developers working in large open-source projects they already knew took 19% longer on average to complete tasks when allowed to use the AI tools available at the time. But METR’s own 2026 update cautioned that its later experiment had selection and measurement problems and was not a reliable estimate of the current productivity effect. Newer models and tools may help developers move faster; the size of that effect remains uncertain.

The conclusion is not that AI always slows development. Rather, AI can speed up one part of the work while increasing human checking, correction and management elsewhere. The first part is highly visible in a demo: code appears in seconds. Real work is finished only after someone checks it against requirements, existing systems, edge cases, security and the consequences of release.

## What is an approval gate protecting, and whose time does it use?

Not every confirmation is a problem. Deleting data, changing production, contacting patients or customers, and publishing an article or advertisement can have consequences that are difficult to reverse. Approval gates can protect safety, privacy, money and public information.

The friction appears when every action is stopped in the same way, regardless of its risk. Even a clearly requested, reversible task—formatting copy or doing local research—can be paused while the AI asks “just to be safe.” The user has to respond, restart the task and wait, without being told what the check is meant to protect.

A gate is not automatically good safety design. Repeated checks with no clear purpose can exhaust people. An exhausted person may even start skimming the checks that matter. Choosing what to verify is not only an efficiency question; it helps preserve attention for genuinely important decisions.

Good safety design should place stops according to risk and reversibility. Low-risk work that can be undone should move forward, with a concise report of the result. An irreversible or externally consequential action should pause and explain the specific impact before requesting approval. Automated tests and diff checks should run where possible, instead of turning every verification step into another question for the user. That is how safety and speed can coexist.

## The invisible work added by AI

AI adoption is often measured by how many lines it generated, how quickly a first draft appeared, or how many tasks ran in parallel. Where do we count the time users spend understanding the output, spotting errors and repeating instructions?

The hidden burden is not only time. There is the mental strain of waiting without knowing what the AI will do next. The attention spent watching for a task that may have stalled. The worry that an earlier decision might be undone again. When users become the managers of AI work, they are repeatedly pulled away from the work they intended to do.

AI may take over routine tasks while returning a different set of tasks to people: directing, monitoring, verifying and correcting. Work has not necessarily disappeared. It may have moved into an unnamed supervisory job.

My own frustration is not simply that AI is imperfect. Some correction is an expected part of using any tool. What wears me down is the unnecessary repetition around that correction: repeating something already explained, revisiting a decision already made, and having to keep instructing a system that is supposed to move the work forward. The problem is not only the error. It is a design that returns the cleanup and process friction to the user.

It is easy to blame the user: “You need to learn how to use AI,” or “Your prompt must have been vague.” Clear requirements and smaller tasks can help. But if the user has already explained the requirements and supplied the context, and the AI still loses them or asks the same question again, the problem is not solely the user’s skill. A good tool should not require people to develop an endless toolkit for managing that tool before it becomes useful.

## Measure the work through to completion

To understand AI’s effect, measure more than generation speed. How long does the task take from request to completion? How many correction rounds were needed? How often did the user repeat the same instruction? How long was the task stalled? Did the AI correct its own mistake, or did a person have to do it? And did the person finish with less effort?

These are questions for users, providers and organizations adopting AI. Users should not mistake an “in progress” indicator for a result. Providers should improve not only the generation experience but also waiting, lost context, verification and rework. Organizations should listen for cognitive load and fatigue, not just count output.

AI is a tool meant to support people. When supervising its judgment, teaching it the right context, noticing when it stops and repeatedly restarting work become the central tasks, the roles have reversed.

If using AI leaves you with no more time, more worry, repeated instructions and the need to keep chasing completion, you do not have to dismiss that feeling as a failure to use it properly. We should ask whether the promise of efficiency has created a new supervisory job for the user—and count the work that has disappeared separately from the work that has merely become harder to see.

Is AI reducing our work?  
Or is it changing the shape of work and returning the checking and worry to us?

## Sources and further reading

### Firsthand accounts from Japan

- [“Why do we feel so tired even though AI coding has made us faster?” (Zenn, March 24, 2026)](https://zenn.dev/shingoirie/articles/210b4f6d73ec6c)
- [“How I Created Hell with AI Coding” (Zenn)](https://zenn.dev/sanyodo/articles/9c2346ef841816)
- [“Cases where AI coding agents make work slower” (Qiita, September 11, 2026)](https://qiita.com/Ohmiya-Mizuki/items/c8471bad8182ed592acd)

### Firsthand accounts from international users

- [“ChatGPT keeps asking for confirmation on completely clear tasks, despite Memory and Custom Instructions” (Reddit, r/OpenAI)](https://www.reddit.com/r/OpenAI/comments/1w0rwpp/chatgpt_keeps_asking_for_confirmation_on/)
- [“Am I getting the stupid version of Cursor?” (Reddit, r/cursor)](https://www.reddit.com/r/cursor/comments/1o10r35/am_i_getting_the_stupid_version_of_cursor/)
- [“What do you do while your coding agents work?” (Reddit, r/cursor)](https://www.reddit.com/r/cursor/comments/1rfpyjn/what_do_you_do_while_your_coding_agents_work/)

### Surveys and research

- Vella, A. & Blincoe, K., [The Impact of AI Coding Assistants on Software Engineering: A Longitudinal Study (arXiv, 2026)](https://arxiv.org/abs/2605.23135) — a longitudinal analysis including a matched cohort of 95 developers. Cited as a preprint, not represented as peer-reviewed research.
- Stack Overflow, [2025 Developer Survey: AI](https://survey.stackoverflow.co/2025/ai) — developer trust in the accuracy of AI output.
- METR, [We are Changing our Developer Productivity Experiment Design (February 2026)](https://metr.org/blog/2026-02-24-uplift-update/) — the 2025 experiment and limitations on interpreting later results.
- METR, [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity (July 2025)](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) — a finding observed under specific developer and task conditions, not a universal estimate of AI productivity.

*Forum posts and technical articles reflect the experiences of individuals who chose to write about them. They are not treated here as representative statistics. Research findings are described with their study populations, conditions and limitations.*
