// init_db.js — contract v0.3 in code. Idempotent: safe to re-run.
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

// mirror_status (v0.2): written by the mirror, no draft/published lifecycle --
// exempt from ensure()'s common-fields schema, so it gets its own validator.
function ensureMirrorStatus() {
  const opts = {
    validator: {
      $jsonSchema: {
        bsonType: "object",
        required: ["mirror_id", "last_seen", "uptime_s", "updated_at"],
        properties: {
          mirror_id: str,
          last_seen: date,
          uptime_s: { bsonType: ["double", "int", "long"] },
          current_page: { bsonType: ["string", "null"] },
          last_sync_at: { bsonType: ["date", "null"] },
          last_error: { bsonType: ["string", "null"] },
          updated_at: date,
        },
      },
    },
    validationLevel: "strict",
    validationAction: "error",
  };
  const name = "mirror_status";
  if (ieee.getCollectionNames().includes(name)) {
    ieee.runCommand({ collMod: name, ...opts });
  } else {
    ieee.createCollection(name, opts);
  }
  ieee[name].createIndex({ mirror_id: 1 }, { unique: true });
  print(`ok: ${name}`);
}
ensureMirrorStatus();

// dashboard_users / audit_log (v0.3): dashboard-only, mirror never reads
// these -- no draft/published lifecycle, so they get their own validators
// too instead of ensure()'s common-fields one.
function ensureSimple(name, schema) {
  const opts = {
    validator: { $jsonSchema: schema },
    validationLevel: "strict",
    validationAction: "error",
  };
  if (ieee.getCollectionNames().includes(name)) {
    ieee.runCommand({ collMod: name, ...opts });
  } else {
    ieee.createCollection(name, opts);
  }
  print(`ok: ${name}`);
}

ensureSimple("dashboard_users", {
  bsonType: "object",
  required: ["username", "password_hash", "role", "created_at", "updated_at"],
  properties: {
    username: str,
    password_hash: str,
    role: { enum: ["admin", "editor"] },
    created_at: date,
    updated_at: date,
  },
});
ieee.dashboard_users.createIndex({ username: 1 }, { unique: true });

ensureSimple("audit_log", {
  bsonType: "object",
  required: ["username", "collection", "document_id", "operation", "at"],
  properties: {
    username: str,
    collection: str,
    document_id: str,
    operation: str,
    at: date,
    changes: { bsonType: ["object", "null"] },
  },
});
ieee.audit_log.createIndex({ at: -1 });
