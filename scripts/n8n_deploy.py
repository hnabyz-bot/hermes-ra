#!/usr/bin/env python3
"""
n8n_deploy.py — Hermes n8n WF 배포 공통 헬퍼
Usage:
  from n8n_deploy import N8nDeploy
  d = N8nDeploy()
  d.patch_node_code(wf_id, node_name, new_jscode)
  d.create_workflow(wf_json)
"""
import os
import sys
import json
import requests

N8N_BASE = os.environ.get("N8N_BASE_URL", "http://localhost:5678/api/v1")
N8N_KEY  = os.environ.get("N8N_API_KEY", "")

class N8nDeploy:
    def __init__(self, base=N8N_BASE, key=N8N_KEY):
        self.base = base
        self.headers = {"X-N8N-API-KEY": key, "Content-Type": "application/json"}

    def _req(self, method, path, **kw):
        r = requests.request(method, self.base + path, headers=self.headers, timeout=30, **kw)
        r.raise_for_status()
        return r.json()

    def get(self, wf_id):
        return self._req("GET", f"/workflows/{wf_id}")

    def deactivate(self, wf_id):
        try:
            self._req("POST", f"/workflows/{wf_id}/deactivate")
        except Exception:
            pass  # already inactive

    def activate(self, wf_id):
        self._req("POST", f"/workflows/{wf_id}/activate")

    def put(self, wf_id, wf):
        payload = {k: wf[k] for k in ("name","nodes","connections","settings","staticData") if k in wf}
        return self._req("PUT", f"/workflows/{wf_id}", json=payload)

    def create(self, wf_json):
        """POST new workflow. Strips read-only fields."""
        for field in ("id","versionId","tags","createdAt","updatedAt","active"):
            wf_json.pop(field, None)
        result = self._req("POST", "/workflows", json=wf_json)
        return result

    def patch_node_code(self, wf_id, node_name, new_jscode, param_key="jsCode"):
        """Find node by name, replace jsCode, PUT back, re-activate."""
        wf = self.get(wf_id)
        was_active = wf.get("active", False)
        node = next((n for n in wf["nodes"] if n["name"] == node_name), None)
        if not node:
            names = [n["name"] for n in wf["nodes"]]
            raise ValueError(f"Node '{node_name}' not found. Available: {names}")
        node["parameters"][param_key] = new_jscode
        self.deactivate(wf_id)
        result = self.put(wf_id, wf)
        if was_active:
            self.activate(wf_id)
        print(f"  ✓ {wf['name']} — node '{node_name}' patched (version={result.get('versionId','?')[:8]})")
        return result

    def patch_node_params(self, wf_id, node_name, param_updates: dict):
        """Update arbitrary parameters on a node."""
        wf = self.get(wf_id)
        was_active = wf.get("active", False)
        node = next((n for n in wf["nodes"] if n["name"] == node_name), None)
        if not node:
            raise ValueError(f"Node '{node_name}' not found.")
        node["parameters"].update(param_updates)
        self.deactivate(wf_id)
        result = self.put(wf_id, wf)
        if was_active:
            self.activate(wf_id)
        print(f"  ✓ {wf['name']} — node '{node_name}' params patched")
        return result

    def list_workflows(self):
        data = self._req("GET", "/workflows?limit=50")
        return [(w["id"], w["name"], w["active"]) for w in data.get("data", [])]


if __name__ == "__main__":
    d = N8nDeploy()
    for wf_id, name, active in d.list_workflows():
        status = "active  " if active else "inactive"
        print(f"  {status} | {wf_id:25} | {name}")
