"""IDOR sweep: log in as client A (alice) and hit every client-B (bob) object URL.

Every object-level request must be 404 (never 200/403/405), list endpoints must
not contain bob's ids, and bob's own signed download link must be useless to alice.
"""

from audit_common import API, api_session, check, creds, done

c = creds()
alice, a_tok = api_session(c["alice"]["email"], c["alice"]["password"])
bob, _ = api_session(c["bob"]["email"], c["bob"]["password"])
B = c["bob"]

resources = {
    "projects": B["project"],
    "messages": B["message"],
    "files": B["file"],
    "invoices": B["invoice"],
}
write = {"X-CSRFToken": a_tok}

print("== list endpoints must not include bob's rows ==")
for name, bob_id in resources.items():
    r = alice.get(f"{API}/api/portal/{name}/", timeout=10)
    ids = {row["id"] for row in r.json().get("results", [])}
    check(f"GET /api/portal/{name}/ excludes bob #{bob_id}", r.status_code == 200 and bob_id not in ids,
          f"{r.status_code} ids={sorted(ids)}")  # fmt: skip
    r = alice.get(f"{API}/api/portal/{name}/", params={"project": B["project"]}, timeout=10)
    if name != "projects":
        check(f"GET /api/portal/{name}/?project=<bob> is empty",
              r.status_code == 200 and r.json()["results"] == [], str(r.status_code))  # fmt: skip

print("\n== every method on bob's objects must be 404 ==")
for name, bob_id in resources.items():
    url = f"{API}/api/portal/{name}/{bob_id}/"
    for method in ("get", "put", "patch", "delete", "post"):
        r = alice.request(method.upper(), url, json={"read": True, "title": "pwned"},
                          headers=write, timeout=10)  # fmt: skip
        check(f"{method.upper():6} {url.replace(API, '')}", r.status_code == 404, str(r.status_code))

for name in ("files", "invoices"):
    url = f"{API}/api/portal/{name}/{resources[name]}/download/"
    r = alice.get(url, timeout=10)
    check(f"GET    {url.replace(API, '')}", r.status_code == 404, str(r.status_code))

thread = f"{API}/api/portal/projects/{B['project']}/messages/"
r = alice.get(thread, timeout=10)
check(f"GET    {thread.replace(API, '')}", r.status_code == 404, str(r.status_code))
r = alice.post(thread, json={"body": "injected by alice"}, headers=write, timeout=10)
check(f"POST   {thread.replace(API, '')}", r.status_code == 404, str(r.status_code))

print("\n== bob's signed download links are useless to alice ==")
for name in ("files", "invoices"):
    link = bob.get(f"{API}/api/portal/{name}/{resources[name]}/download/", timeout=10).json()["url"]
    path = "/" + link.split("/", 3)[3]
    own = bob.get(f"{API}{path}", timeout=10)
    stolen = alice.get(f"{API}{path}", timeout=10)
    check(f"bob downloads own {name[:-1]}", own.status_code == 200, str(own.status_code))
    check(f"alice replays bob's {name[:-1]} link", stolen.status_code == 404, str(stolen.status_code))

print("\n== bob's data is unchanged ==")
r = bob.get(f"{API}/api/portal/projects/{B['project']}/messages/", timeout=10)
bodies = [m["body"] for m in r.json()["results"]]
check("no message injected into bob's thread", "injected by alice" not in bodies, str(bodies))
done()
