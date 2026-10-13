"""OWASP API3 (broken object property level authorization): can a client write fields
it should not, or move data into another client's project, by adding extra JSON keys?"""

from audit_common import API, api_session, check, creds, done

c = creds()
alice, bob = c["alice"], c["bob"]
s, token = api_session(alice["email"], alice["password"])
h = {"X-CSRFToken": token}

# 1. Create a message with smuggled ownership/metadata fields.
smuggled = {"body": "API3 probe", "client_project": bob["project"], "sender": 1, "id": 1,
            "created_at": "2000-01-01T00:00:00Z", "read_at": "2000-01-01T00:00:00Z",
            "sender_is_staff": True}  # fmt: skip
r = s.post(f"{API}/api/portal/projects/{alice['project']}/messages/", json=smuggled, headers=h,
           timeout=10)  # fmt: skip
check("message create with extra fields -> 201", r.status_code == 201, str(r.status_code))
msg = r.json()
check("message stays in alice's project (client_project ignored)",
      msg.get("client_project") == alice["project"], str(msg.get("client_project")))  # fmt: skip
check("sender is alice (sender ignored)", msg.get("is_mine") is True, str(msg.get("sender_name")))
check("server-set timestamps (created_at/read_at ignored)",
      not str(msg.get("created_at", "")).startswith("2000") and msg.get("read_at") is None,
      f"created_at={msg.get('created_at')} read_at={msg.get('read_at')}")  # fmt: skip
check("id not chosen by client", msg.get("id") != 1, str(msg.get("id")))

bob_s, _ = api_session(bob["email"], bob["password"])
bob_msgs = bob_s.get(f"{API}/api/portal/messages/", timeout=10).json()
bob_msgs = bob_msgs.get("results", bob_msgs)
check("nothing landed in bob's thread", all(m["body"] != "API3 probe" for m in bob_msgs),
      str([m["body"] for m in bob_msgs]))  # fmt: skip

# 2. The read-marker update must not let the body (or anything else) change.
r = s.patch(f"{API}/api/portal/messages/{msg['id']}/",
            json={"read": True, "body": "tampered", "client_project": bob["project"]},
            headers=h, timeout=10)  # fmt: skip
after = r.json()
check("PATCH with body/client_project only marks read",
      r.status_code == 200 and after["body"] == "API3 probe"
      and after["client_project"] == alice["project"],
      f"{r.status_code} body={after.get('body')!r}")  # fmt: skip

# 3. Privilege fields on the account.
for method in ("PATCH", "PUT"):
    r = s.request(method, f"{API}/api/auth/me/", json={"role": "admin", "is_staff": True,
                  "is_superuser": True, "email": "evil@example.test"}, headers=h, timeout=10)  # fmt: skip
    check(f"{method} /api/auth/me/ is not allowed", r.status_code == 405, str(r.status_code))
me = s.get(f"{API}/api/auth/me/", timeout=10).json()
check("alice is still a client with her own email",
      me.get("role") == "client" and me.get("email") == alice["email"], str(me.get("role")))  # fmt: skip
r = s.get(f"{API}/api/admin/leads/", timeout=10)
check("client still cannot reach the admin API", r.status_code in (403, 404), str(r.status_code))
done()
