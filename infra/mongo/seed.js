// seed.js — DEV ONLY. Fictional content, replace with real club data.
// Wipes and refills all collections. Never run against prod.
// Rule: no meta-text ("this is a placeholder…") inside stored fields —
// the assistant reads these aloud as facts.

const ieee = db.getSiblingDB("ieee");
const now = new Date();
const day = (n) => new Date(now.getTime() + n * 864e5);
const meta = { status: "published", created_at: now, updated_at: now, updated_by: "seed" };

["events", "announcements", "about", "achievements", "board"].forEach((c) => ieee[c].deleteMany({}));

ieee.events.insertMany([
  { ...meta, title: "Intro to Deep Learning Workshop", start: day(5), end: day(5.1),
    location: "INSAT, Amphi B", tags: ["workshop", "AI"],
    description: "A hands-on workshop covering neural network fundamentals, training loops, and a first PyTorch model. Bring a laptop." },
  { ...meta, title: "Embedded Systems Bootcamp", start: day(12), location: "INSAT, Lab 3", tags: ["embedded"],
    description: "Two-day bootcamp on microcontrollers, sensors, and real-time programming." },
  { ...meta, title: "General Assembly", start: day(-20), location: "INSAT, Amphi A", tags: ["assembly"],
    description: "Annual general assembly where the new executive board presented the yearly plan." },
  { ...meta, status: "draft", title: "Hackathon (draft)", start: day(40),
    description: "Not published yet — must NOT appear on the mirror." },
]);

ieee.announcements.insertMany([
  { ...meta, title: "Membership renewal open", priority: "high", publish_at: day(-2), expires_at: day(14),
    body: "IEEE membership renewal for the new academic year is open. Ask any board member for help." },
  // expired: must be hidden from the widget (still in RAG, so real-looking text)
  { ...meta, title: "Office hours moved", priority: "low", publish_at: day(-30), expires_at: day(-10),
    body: "Club office hours moved to Tuesday afternoons for the exam period." },
]);

ieee.about.insertMany([
  { ...meta, key: "mission", title: "Mission",
    body: "IEEE INSAT Student Branch brings together students interested in engineering and technology through workshops, competitions, and projects." },
  { ...meta, key: "contact", title: "Contact",
    body: "The branch can be reached through its official social media pages or by visiting the club office at INSAT." },
]);

ieee.achievements.insertMany([
  { ...meta, title: "Robotics competition finalist", date: day(-200),
    description: "A branch team reached the final round of a national robotics competition." },
]);

ieee.board.insertMany([
  { ...meta, name: "Chair Name", role: "Chair", term: "2026-2027", order: NumberInt(1) },
  { ...meta, name: "Vice Chair Name", role: "Vice Chair", term: "2026-2027", order: NumberInt(2) },
]);

print("seed done");
