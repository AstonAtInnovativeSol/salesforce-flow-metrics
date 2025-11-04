# GitHub Actions Authentication Setup Guide

## ✅ How It Works

### **Local Execution (Your Machine)**
- ✅ Scripts use `sf_config.py` from your local machine
- ✅ `sf_config.py` is **gitignored** - never committed to GitHub
- ✅ Your credentials stay on your machine only
- ✅ Scripts work automatically when run locally

### **GitHub Actions (Automated Runs)**
- ✅ Scripts use environment variables from GitHub Secrets
- ✅ No credentials in code or repository
- ✅ GitHub Secrets are encrypted and secure
- ✅ Scripts automatically detect which environment they're in

---

## 🔧 Setup Steps

### **Step 1: Configure GitHub Secrets**

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

   **Secret Name:** `SF_USERNAME`
   **Secret Value:** `your-username@example.com`

   **Secret Name:** `SF_CONSUMER_KEY`
   **Secret Value:** `3MVG9...` (your Connected App Consumer Key)

   **Secret Name:** `SF_DOMAIN`
   **Secret Value:** `login` (or `test` for sandbox)

   **Secret Name:** `SF_PRIVATE_KEY`
   **Secret Value:** (paste entire content of your `.pem` private key file)

### **Step 2: Update Scripts to Use Config Helper**

Scripts will automatically:
- ✅ Try `sf_config.py` first (local execution)
- ✅ Fall back to environment variables (GitHub Actions)
- ✅ Work in both environments without code changes

### **Step 3: Test GitHub Actions**

1. Create `.github/workflows/run_scripts.yml` (already created)
2. Push to GitHub
3. Go to **Actions** tab to see workflow runs
4. Scripts will authenticate using GitHub Secrets

---

## 📋 Example Script Update

### **Before (sf_config.py only):**
```python
import sf_config

def get_jwt_token():
    with open(sf_config.PRIVATE_KEY_FILE, "r") as f:
        private_key = f.read()
    # ... rest of code
```

### **After (supports both):**
```python
from sf_config_helper import get_sf_config

def get_jwt_token():
    config = get_sf_config()
    private_key = config.get_private_key()
    # ... rest of code uses config.SF_USERNAME, config.SF_CONSUMER_KEY, etc.
```

---

## 🔒 Security Notes

✅ **Local execution:** Uses `sf_config.py` (gitignored, never committed)
✅ **GitHub Actions:** Uses GitHub Secrets (encrypted, never exposed)
✅ **No credentials in code:** Ever
✅ **Works automatically:** Scripts detect environment

---

## ⚠️ Important

- **GitHub Actions will NOT work** without configuring GitHub Secrets
- **Local execution continues to work** as-is with `sf_config.py`
- **You must configure secrets** for automated runs to authenticate

---

## 🚀 Next Steps

1. ✅ Configure GitHub Secrets (Step 1 above)
2. ⚠️ Update scripts to use `sf_config_helper.py` (optional - can be done gradually)
3. ✅ Test workflow in GitHub Actions tab

**Current Status:** Scripts work locally. For GitHub Actions, you'll need to:
- Configure secrets (required)
- Optionally update scripts to use config helper (for seamless dual support)

