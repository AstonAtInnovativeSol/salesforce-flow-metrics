# GitHub Secrets - Exact Field Names

Based on your `sf_config.py` file, here are the **exact GitHub Secrets** you need to configure:

## ✅ Required GitHub Secrets

### **1. SF_USERNAME**
- **Value:** `afleming@innovativesol.com` (your actual username)
- **From:** `sf_config.py` → `SF_USERNAME`

### **2. SF_CONSUMER_KEY**
- **Value:** `3MVG98XJQQAccJQcGc5mps7vpffypZRfdV4YWfQxNgp0KKK9lfalkEE3Tbz1AFJdm2QLUzFxGEvIwUbfNBE1p` (your actual key)
- **From:** `sf_config.py` → `SF_CONSUMER_KEY`

### **3. SF_DOMAIN**
- **Value:** `login` (or `test` for sandbox)
- **From:** `sf_config.py` → `SF_DOMAIN`

### **4. SF_PRIVATE_KEY**
- **Value:** Entire content of your `.pem` file (copy/paste the whole file)
- **From:** Read the file at `/Users/afleming/Desktop/Salesforce_Reports/salesforce_private_key.pem`
- **Note:** This is the **content** of the file, not the path

## 📋 Summary

| GitHub Secret Name | Source in sf_config.py | Value Location |
|-------------------|------------------------|----------------|
| `SF_USERNAME` | `SF_USERNAME` | `afleming@innovativesol.com` |
| `SF_CONSUMER_KEY` | `SF_CONSUMER_KEY` | Your Connected App Consumer Key |
| `SF_DOMAIN` | `SF_DOMAIN` | `login` |
| `SF_PRIVATE_KEY` | `PRIVATE_KEY_FILE` | Read content from `.pem` file |

## 🔍 How to Get SF_PRIVATE_KEY Value

1. Open the file: `/Users/afleming/Desktop/Salesforce_Reports/salesforce_private_key.pem`
2. Copy the **entire content** (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`)
3. Paste it as the value for `SF_PRIVATE_KEY` secret in GitHub

## ⚠️ Important Notes

- ✅ Field names match exactly: `SF_USERNAME`, `SF_CONSUMER_KEY`, `SF_DOMAIN`
- ✅ `SF_PRIVATE_KEY` is the **content** (not the path like `PRIVATE_KEY_FILE`)
- ❌ `SF_INSTANCE_URL` is **not needed** for GitHub Actions (auto-detected)
- ✅ All secrets are encrypted by GitHub

---

**Your exact configuration matches perfectly!** ✅

