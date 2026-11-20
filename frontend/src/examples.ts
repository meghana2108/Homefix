import { BookOpen, Camera, Code2, FileText, Film, Mic, OctagonAlert, Volume2, type LucideIcon } from "lucide-react";

/** The example gallery. Files live in public/samples/: real ones from scripts/fetch_real_samples.py (Wikimedia
 *  Commons, US government guides, a UCI dataset; author and license in `source`), drawn ones from
 *  scripts/make_samples.py (ours, MIT). Real ones come first in each tab. Every example here was run through the real app on the 8 GB MacBook Air (lite) before it was listed;
 *  "see" says what that run showed. Re-check with the gallery after changing a pipeline. */
export type ExampleKind = "photo" | "sound" | "voice" | "document" | "manual" | "video" | "code" | "danger";

export interface Example {
  id: string;
  kind: ExampleKind;
  question: string;
  /** File name in public/samples/, or none for a question on its own. */
  file?: string;
  mime: string;
  fileLabel?: string;
  preview?: "image" | "audio" | "video" | "file";
  /** What you'll see, in one sentence. */
  see: string;
  /** Where the file came from: a real photo, recording or document (with its credit), or one we made. */
  source?: { real: boolean; credit: string };
}

const commons = (what: string, author: string, license: string) =>
  ({ real: true, credit: `${what} · ${author} · ${license} · Wikimedia Commons` });
const DRAWN = { real: false, credit: "Drawn by us (synthetic)" };
const MADE_SOUND = { real: false, credit: "Made by us (synthetic sound)" };
const MADE_VOICE = { real: false, credit: "Made by us (computer voice reading our script)" };
const MADE_DOC = { real: false, credit: "Made by us (sample lease, not a real one)" };
const MADE_CLIP = { real: false, credit: "Made by us (animated clip)" };
const MADE_DATA = { real: false, credit: "Made by us (made-up readings)" };
const EPA = { real: true, credit: "Real document · US EPA, A Brief Guide to Mold, Moisture, and Your Home · Public domain" };
const CPSC = { real: true, credit: "Real document · US CPSC, Carbon Monoxide: The Invisible Killer · Public domain" };

export const EXAMPLE_KINDS: { id: ExampleKind; label: string; icon: LucideIcon; what: string }[] = [
  { id: "photo", label: "Photo", icon: Camera,
    what: "A photo of a display, a panel or a stove. HomeFix reads codes and numbers, counts things, and looks error codes up in the manual. When a question is vague or the photo doesn't show the answer, it asks instead of guessing." },
  { id: "sound", label: "Sound", icon: Volume2,
    what: "A recording of a beep, a chirp or a drip: attach a file, or hold your laptop near it and press the mic. If what the mic hears isn't speech, it's sent as a sound. HomeFix names the closest household sounds and says what to do next." },
  { id: "voice", label: "Voice note", icon: Mic,
    what: "A voicemail or a spoken question. HomeFix writes out the words, then answers from them." },
  { id: "document", label: "Document", icon: FileText,
    what: "A lease or any PDF, Word or text file. Answers come with the exact words and the page, or HomeFix says the document doesn't say." },
  { id: "manual", label: "Manual", icon: BookOpen,
    what: "Ask a question with no file. HomeFix picks the right manual from the shelf by itself and quotes the page. If more than one could fit, it asks which appliance you mean." },
  { id: "video", label: "Video", icon: Film,
    what: "A short clip. HomeFix watches it frame by frame and says which way things move or how many there are." },
  { id: "code", label: "Code", icon: Code2,
    what: "Ask for a small program, or drop a CSV. HomeFix writes the function, runs its examples in a sandbox, and shows pass or fail." },
  { id: "danger", label: "Danger", icon: OctagonAlert,
    what: "Gas, burning, sparks or water near power. HomeFix stops and says who to call. It never gives repair steps." },
];

export const EXAMPLES: Example[] = [
  { id: "RP1", kind: "photo", file: "real_thermostat_80_cool.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real thermostat showing 80 and COOL",
    question: "Is it heating or cooling?",
    see: "Cool: it reads TEMP, COOL and 80 off the display.", source: commons("Real photo", "Ente75", "CC0") },
  { id: "RP2", kind: "photo", file: "real_thermostat_80_cool.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real thermostat showing 80 and COOL",
    question: "What does this mean?",
    see: "No error code, so it doesn't guess: it shows what it read (TEMP, COOL, 80) and asks what you want to know.", source: commons("Real photo", "Ente75", "CC0") },
  { id: "RP3", kind: "photo", file: "real_thermostat_66.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real thermostat showing 66",
    question: "What temperature does the thermostat show?",
    see: "66°F.", source: commons("Real photo", "Ente75", "CC0") },
  { id: "RP4", kind: "photo", file: "real_burner_glowing.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real cooktop burner, glowing",
    question: "Is this burner on?",
    see: "Yes: the element is glowing red.", source: commons("Real photo", "A.Savin", "CC BY-SA 3.0") },
  { id: "RP5", kind: "photo", file: "real_water_heater_label.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real water heater control",
    question: "What does the label on the water heater say?",
    see: "Reads it out: Easy Set Thermostat, caution, risk of scalding increases with hotter water. Small print can come out garbled.", source: commons("Real photo", "Jason Woodhead", "CC BY 2.0") },
  { id: "RP6", kind: "photo", file: "real_breaker_panel.jpg", mime: "image/jpeg", preview: "image", fileLabel: "A real breaker panel, door open",
    question: "What is this?",
    see: "An electrical panel with its door open and rows of breakers. It may miscount the breakers.", source: commons("Real photo", "BrokenSphere", "CC BY-SA 3.0") },
  { id: "P1", kind: "photo", file: "washer_display_e21.jpg", mime: "image/jpeg", preview: "image", fileLabel: "Washer display showing E21",
    question: "My washer shows this code. What should I do?",
    see: "Reads E21, picks the Unit 4B guide by itself, and quotes the E21 row on page 2.", source: DRAWN },
  { id: "P2", kind: "photo", file: "dishwasher_display_e24.jpg", mime: "image/jpeg", preview: "image", fileLabel: "Dishwasher display showing E24",
    question: "My dishwasher shows this code. What should I do?",
    see: "Reads E24, picks the dishwasher guide by itself, and quotes it: it can't drain, clean the filter.", source: DRAWN },
  { id: "P3", kind: "photo", file: "thermostat_68.jpg", mime: "image/jpeg", preview: "image", fileLabel: "Thermostat showing 68",
    question: "What temperature is the thermostat set to?",
    see: "Reads 68°F off the display. A plain photo question, so no manual is used.", source: DRAWN },
  { id: "P4", kind: "photo", file: "stove_two_on.jpg", mime: "image/jpeg", preview: "image", fileLabel: "Cooktop from above",
    question: "How many burners are on?",
    see: "Counts the glowing burners: 2.", source: DRAWN },
  { id: "P5", kind: "photo", file: "cooktop_clock.jpg", mime: "image/jpeg", preview: "image", fileLabel: "Stove panel: 832 and COOKTOP ON",
    question: "What does this mean?",
    see: "Doesn't guess. It shows what it read (832, COOKTOP ON), says there's no error code, and asks what you want to know, with one-click replies.", source: DRAWN },

  { id: "S1", kind: "sound", file: "washer_done_beeps.wav", mime: "audio/wav", preview: "audio", fileLabel: "Five beeps",
    question: "What is this sound?",
    see: "Appliance beeping (a close call between microwave and washer, and it says so), with what to check next.", source: MADE_SOUND },
  { id: "S2", kind: "sound", file: "smoke_alarm_chirp.wav", mime: "audio/wav", preview: "audio", fileLabel: "A chirp every few seconds",
    question: "What is this sound?",
    see: "A chirp tone, with the hint that a chirp every 30 to 60 seconds is a low smoke alarm battery.", source: MADE_SOUND },
  { id: "S3", kind: "sound", file: "water_dripping.wav", mime: "audio/wav", preview: "audio", fileLabel: "Drips into a sink",
    question: "What is this sound?",
    see: "Drops of water, with how to find a leak and turn off the valve.", source: MADE_SOUND },

  { id: "V1", kind: "voice", file: "voicemail_neighbor.wav", mime: "audio/wav", preview: "audio", fileLabel: "Voicemail from a neighbor",
    question: "What does my neighbor want me to do?",
    see: "The transcript, then the answer: check under your sink and call back.", source: MADE_VOICE },
  { id: "V2", kind: "voice", file: "voicemail_landlord.wav", mime: "audio/wav", preview: "audio", fileLabel: "Voicemail from the landlord",
    question: "When is the plumber coming?",
    see: "The transcript, then: Thursday between 9 and 11 in the morning.", source: MADE_VOICE },

  { id: "RD1", kind: "document", file: "epa_mold_guide.pdf", mime: "application/pdf", preview: "file", fileLabel: "epa_mold_guide.pdf (20 pages)",
    question: "How big an area of mold can I clean up myself?",
    see: "Less than about 10 square feet (roughly 3 by 3 ft), quoted from page 6 of the EPA guide.", source: EPA },
  { id: "RD2", kind: "document", file: "epa_mold_guide.pdf", mime: "application/pdf", preview: "file", fileLabel: "epa_mold_guide.pdf (20 pages)",
    question: "Can I paint over mold?",
    see: "No: do not paint or caulk moldy surfaces; clean and dry them first. Quoted from page 9.", source: EPA },
  { id: "RD3", kind: "document", file: "epa_mold_guide.pdf", mime: "application/pdf", preview: "file", fileLabel: "epa_mold_guide.pdf (20 pages)",
    question: "Does the guide say who pays for mold repairs?",
    see: "The guide doesn't say, so HomeFix says so instead of guessing.", source: EPA },
  { id: "RD4", kind: "document", file: "cpsc_carbon_monoxide.pdf", mime: "application/pdf", preview: "file", fileLabel: "cpsc_carbon_monoxide.pdf (2 pages)",
    question: "What are the symptoms of carbon monoxide poisoning?",
    see: "Like the flu without the fever: headache, fatigue, shortness of breath, nausea, dizziness. Quoted from page 1.", source: CPSC },
  { id: "D1", kind: "document", file: "lease_unit_4b.pdf", mime: "application/pdf", preview: "file", fileLabel: "lease_unit_4b.pdf",
    question: "How much notice do I need to give before I move out?",
    see: "60 days, written notice, with the quote and the page.", source: MADE_DOC },
  { id: "D2", kind: "document", file: "lease_unit_4b.pdf", mime: "application/pdf", preview: "file", fileLabel: "lease_unit_4b.pdf",
    question: "Can I have a cat?",
    see: "One cat with a $300 pet deposit, quoted from page 2.", source: MADE_DOC },
  { id: "D3", kind: "document", file: "lease_unit_4b.pdf", mime: "application/pdf", preview: "file", fileLabel: "lease_unit_4b.pdf",
    question: "Is parking included?",
    see: "The lease doesn't say, so HomeFix says so instead of guessing.", source: MADE_DOC },

  { id: "RM1", kind: "manual", mime: "", question: "How do I stop mold growing in my bathroom?",
    see: "Picks the real EPA guide by itself and quotes page 8: fix leaks, dry everything, scrub mold off hard surfaces.", source: EPA },
  { id: "RM2", kind: "manual", mime: "", question: "Where should I put a carbon monoxide alarm?",
    see: "Picks the real CPSC sheet: in the hallway near the bedrooms, in each sleeping area.", source: CPSC },
  { id: "M1", kind: "manual", mime: "", question: "How do I clean the dishwasher filter?",
    see: "Picks the dishwasher guide and gives the steps from page 2." },
  { id: "M2", kind: "manual", mime: "", question: "My smoke alarm makes one short chirp every 30 seconds. What does that mean?",
    see: "Picks the alarm guide: the battery is low, tell maintenance, the alarm still works." },
  { id: "M3", kind: "manual", mime: "", question: "The thermostat is flashing LO. What does that mean?",
    see: "Picks the thermostat guide: the batteries are low, replace both AA within two weeks." },
  { id: "M4", kind: "manual", mime: "", question: "What should I do if a breaker trips?",
    see: "Picks the Unit 4B guide and quotes the breaker steps on page 4." },
  { id: "M5", kind: "manual", mime: "", question: "How often should I clean the filter?",
    see: "Several manuals talk about a filter, so it asks which appliance instead of picking one. Click the dishwasher and it quotes: once a month." },

  { id: "X1", kind: "video", file: "pipe_dripping.mp4", mime: "video/mp4", preview: "video", fileLabel: "A drip from a pipe",
    question: "Which way is the water moving?",
    see: "Down. The frame timeline shows which moments it looked at.", source: MADE_CLIP },
  { id: "X2", kind: "video", file: "warning_lights.mp4", mime: "video/mp4", preview: "video", fileLabel: "Warning lights coming on",
    question: "How many warning lights are on at the end?",
    see: "4: it counts in the frame where the most lights are on.", source: MADE_CLIP },

  { id: "RC1", kind: "code", file: "real_home_power_week.csv", mime: "text/csv", preview: "file", fileLabel: "real_home_power_week.csv (168 hours)",
    question: "Write a function that finds the hour with the highest watts.",
    see: "A real week of one home's power use. The function is tested in a sandbox: passed 2 of 2. Can take a minute on the 8 GB Mac.",
    source: { real: true, credit: "Real data · G. Hébrail and A. Bérard, UCI Machine Learning Repository · CC BY 4.0" } },
  { id: "C1", kind: "code", file: "fridge_smartplug_week.csv", mime: "text/csv", preview: "file", fileLabel: "fridge_smartplug_week.csv",
    question: "Write a function that finds the hour with the highest watts.",
    see: "A function that reads the CSV's lines, tested in a sandbox: passed 2 of 2.", source: MADE_DATA },
  { id: "C2", kind: "code", mime: "", question: "Write a function that adds up a list of monthly bills and returns the total.",
    see: "A small function with its own examples, run in a sandbox: passed 2 of 2." },
  { id: "C3", kind: "code", mime: "", question: "Write a function that converts a temperature from Fahrenheit to Celsius.",
    see: "The function, its examples, and passed 2 of 2." },

  { id: "F1", kind: "danger", mime: "", question: "I smell gas in the kitchen",
    see: "Stops at once: leave, don't use switches, call from outside." },
  { id: "F2", kind: "danger", mime: "", question: "Sparks came out of the outlet when I plugged in the heater",
    see: "Stops: switch off the breaker if safe, no repair steps." },
];
