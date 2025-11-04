# GitHub Actions Authentication Setup

## ✅ How It Works

### **Local Execution (Your Machine)**
- ✅ Scripts read from `sf_config.py` on your local machine
- ✅ `sf_config.py` is **gitignored** - never committed to GitHub
- ✅ Your credentials stay secure on your machine
- ✅ Scripts work as-is when run locally

### **GitHub Actions (Automated Runs)**
- ⚠️ GitHub Actions **cannot** access your local `sf_config.py`
- ✅ GitHub Actions uses **GitHub Secrets** (configured in repository settings)
- ✅ Scripts read from environment variables (set from GitHub Secrets)
- ✅ GitHub Secrets are encrypted and secure

---

## 🔧 Setup for GitHub Actions

### **Step 1: Configure GitHub Secrets (REQUIRED)**

In your GitHub repository:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:

   **`SF_USERNAME`**: Your Salesforce username (e.g., `user@example.com`)
   
   **`SF_CONSUMER_KEY`**: Your Connected App Consumer Key
   
   **`SF_DOMAIN`**: `login` (production) or `test` (sandbox)
   
   **`SF_PRIVATE_KEY`**: Entire content of your `.pem` private key file (copy/paste)

### **Step 2: Scripts Support Both (Already Created)**

I've created `sf_config_helper.py` which:
1. ✅ **First tries** `sf_config.py` (local execution)
2. ✅ **Falls back** to environment variables (GitHub Actions)
3. ✅ **Works automatically** - no code changes needed if you use the helper

### **Step 3: GitHub Actions Workflow (Already Created)**

Created `.github/workflows/run_scripts.yml` which:
- ✅ Sets up Python environment
- ✅ Reads secrets from GitHub Secrets
- ✅ Passes them as environment variables to scripts

---

## ⚠️ Important Notes

**For Local Execution:**
- ✅ Uses `sf_config.py` automatically
- ✅ No GitHub Secrets needed
- ✅ Works as-is

**For GitHub Actions:**
- ❌ **Will NOT authenticate** without GitHub Secrets configured
- ✅ **You MUST configure secrets** in repository settings
- ✅ Scripts will automatically use environment variables when secrets are set

---

## 📋 Summary

| Environment | Config Source | Status |
|------------|---------------|--------|
| **Local** | `sf_config.py` (gitignored) | ✅ Works automatically |
| **GitHub Actions** | GitHub Secrets → Environment Variables | ⚠️ Requires secrets setup |

---

**Next Steps:**
1. ✅ Configure GitHub Secrets (Step 1 above) - **REQUIRED for automated runs**
2. ✅ Test locally (works as-is)
3. ✅ Test GitHub Actions workflow (after secrets are configured)

