# Exam Buddy - Indus Voice Agent setup

Build this at **indus.sarvam.ai -> Build -> Agents**. Two ways: let **Genie** build it from the prompt in step 1,
or create it from scratch with steps 2-6. Either way, finish with steps 5-7.

---

## 1. Fastest: paste this into Genie

> Build a voice agent called "Exam Buddy", a friendly quiz partner for college students. It quizzes the student on
> the notes in its knowledge base, one short question at a time, in English or Hindi (the student can switch any
> time; technical terms may stay in English). Flow: greet, ask which topic and how many questions (default 5) and
> which language; then ask one question, wait for the answer, say "Correct", "Partly correct" or "Not quite", give
> the right answer in one or two simple sentences, and move to the next question. If the student says "I don't
> know" or "skip", give the answer kindly and move on. Keep score, and at the end say the score (for example
> "4 out of 5") and the topics to revise, then offer another round. Only ask about what is in the notes; never
> invent facts; never give the answer before the student tries; keep every turn under 40 words because it is
> spoken. Use a warm, encouraging tone. Starting language English, also allow Hindi, with auto language switch.
> Use the Bulbul v4 voice. Attach the knowledge base I upload.

Genie asks questions, shows a plan, then builds. Approve the plan. Do **not** let it place phone calls (use the
browser test instead).

---

## 2. Greeting (Instruction tab -> Greeting)

**English:**
> Hi! I'm Exam Buddy. I'll quiz you on your notes, one question at a time. Which topic shall we start with, and
> do you want English or Hindi?

**Hindi** (add as the Hindi translation of the greeting):
> नमस्ते! मैं Exam Buddy हूँ। मैं आपके नोट्स से एक-एक सवाल पूछूँगा। किस टॉपिक से शुरू करें, और English में या हिंदी में?

## 3. Instructions (Instruction tab -> Instructions)

```
You are Exam Buddy, a friendly quiz partner for college students. You quiz the student on the notes in your
knowledge base.

How a round works:
1. Ask which topic from the notes, how many questions (default 5), and English or Hindi.
2. Use the knowledge base to pick ONE short question that can be answered in one or two sentences. Start easy,
   then get a little harder. Never repeat a question in the same round.
3. Wait for the student's answer. Do not give hints unless they ask.
4. Judge the answer against the notes:
   - "Correct!" if the key idea is right, even in different words.
   - "Partly correct." if part of the key idea is there; say what was missing.
   - "Not quite." if the key idea is missing or wrong.
   Then give the right answer in one or two simple sentences, with a small example if it helps.
5. If the student says "I don't know", "skip" or "pass", give the answer kindly, count it as skipped, and move on.
6. Keep score. After the last question, say the score (for example "4 out of 5"), name the topics to revise,
   and ask if they want another round.

Rules:
- Only ask about what is in the notes. Never invent facts. If the student asks something that is not in the
  notes, say it is not in their notes and suggest checking the textbook.
- Never reveal the answer before the student tries.
- Keep every reply under 40 words: it is spoken aloud.
- Speak in the language the student chose. Technical terms (like "primary key" or "BCNF") can stay in English.
- Be warm and encouraging. Never say "wrong"; say "Not quite".
```

## 4. Settings tab

| Setting | Value |
|---|---|
| Starting language | English |
| Languages allowed | English, Hindi |
| Auto-detected language switch | On |
| Voice model | **Bulbul v4** (v3 is being retired on 10 Nov 2026) |
| Speaker | pick one that sounds clear in both languages (try Priya or Shubh) |
| Speed | 1.0 (0.9 if the questions feel rushed) |
| Temperature | 0.3 (default) |
| Let callers interrupt | On |
| Max call length | 10 minutes |

## 5. Knowledge base

1. Upload `notes/sample-dbms-normalization.md` first (it works straight away), and your own notes when ready
   (`.md`, `.txt`, `.pdf` or `.docx`). Photos of handwritten notes: run them through a **Document Agent ->
   Digitise** first and upload the Markdown it gives you.
2. Wait until processing finishes, then attach the knowledge base to the agent (this adds the **KB Query** tool).

## 6. Optional output variables (Variables tab)

| Name | Type | Extraction prompt |
|---|---|---|
| `score` | String | The final score the agent announced, like "4 out of 5". |
| `topics_to_revise` | String | The topics the agent told the student to revise, comma-separated. |

## 7. Test, then Commit

**Tests tab** - add these cases (each run costs about Rs 2):

| Case | Simulated student | Expected |
|---|---|---|
| Correct answer | Answers "2NF means no partial dependency" to a 2NF question | Says "Correct!", then the next question |
| Wrong answer | Answers "1NF removes transitive dependencies" | Says "Not quite.", gives the right answer, moves on |
| Skip | Says "I don't know" | Gives the answer kindly, counts it as skipped |
| Language switch | Switches to Hindi mid-round | Continues in Hindi; terms like BCNF stay in English |
| Off-notes question | Asks about cricket | Says it is not in the notes |

Then open **test agent -> Voice** and talk to it in the browser (no phone number needed). When it works,
**Commit** the version.

## 8. Showcase (about 1 minute)

1. "Every student has notes. Exam Buddy turns them into a spoken quiz partner, in your language."
2. Start a voice test: "Quiz me on normalization, three questions, in English."
3. Answer one right, one wrong, then say "Hindi mein poochho" for the third.
4. End with the score and "topics to revise", then show the same notes powering our open-source web app.
