// init_db.js — contract v0.1 in code. Idempotent: safe to re-run.
// Run: mongosh "mongodb://localhost:27017/?directConnection=true" init_db.js

const ieee = db.getSiblingDB("ieee");

const str = { bsonType: "string", minLength: 1 };
const date = { bsonType: "date" };

const common = {
  status: { enum: ["draft", "published"] },
  created_at: date,
  updated_at: date,
  updated_by: str,
};
const commonReq = ["status", "created_at", "updated_at", "updated_by"];

function ensure(name, props, required, indexes = []) {
  const opts = {
    validator: {
      $jsonSchema: {
        bsonType: "object",
        required: [...commonReq, ...required],
        properties: { ...common, ...props },
      },
    },
    validationLevel: "strict",
    validationAction: "error",
  };
  if (ieee.getCollectionNames().includes(name)) {
    ieee.runCommand({ collMod: name, ...opts });
  } else {
    ieee.createCollection(name, opts);
  }
  ieee[name].createIndex({ updated_at: 1 });
  ieee[name].createIndex({ status: 1 });
  indexes.forEach(([keys, o]) => ieee[name].createIndex(keys, o || {}));
  print(`ok: ${name}`);
}

ensure("events", {
  title: str,
  description: str,
  start: date,
  end: date,
  location: { bsonType: "string" },
  tags: { bsonType: "array", items: { bsonType: "string" } },
  registration_url: { bsonType: "string" },
  image_url: { bsonType: "string" },
}, ["title", "description", "start"], [[{ start: 1 }]]);

ensure("announcements", {
  title: str,
  body: str,
  publish_at: date,
  expires_at: date,
  priority: { enum: ["low", "normal", "high"] },
}, ["title", "body", "publish_at", "priority"], [[{ publish_at: 1 }]]);

ensure("about", {
  key: str,
  title: str,
  body: str,
}, ["key", "title", "body"], [[{ key: 1 }, { unique: true }]]);

ensure("achievements", {
  title: str,
  date: date,
  description: str,
}, ["title", "date", "description"], [[{ date: -1 }]]);

ensure("board", {
  name: str,
  role: str,
  term: str,
  order: { bsonType: "int" },
  email: { bsonType: "string" },
}, ["name", "role", "term", "order"], [[{ order: 1 }]]);
