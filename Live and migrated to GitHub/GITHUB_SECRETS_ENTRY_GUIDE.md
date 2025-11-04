# GitHub Secrets Entry Guide - Exact Values

## ✅ NO QUOTES NEEDED

When entering secrets in GitHub Secrets, enter **only the value** - **no quotes**.

---

## 📋 Exact Values to Enter

### **1. SF_USERNAME**
**In GitHub Secrets:**
```
afleming@innovativesol.com
```

**NOT:**
```
'afleming@innovativesol.com'  ❌ (Don't include quotes)
```

---

### **2. SF_CONSUMER_KEY**
**In GitHub Secrets:**
```
3MVG98XJQQAccJQcGc5mps7vpffypZRfdV4YWfQxNgp0KKK9lfalkEE3Tbz1AFJdm2QLUzFxGEvIwUbfNBE1p
```

**NOT:**
```
'3MVG98XJQQAccJQcGc5mps7vpffypZRfdV4YWfQxNgp0KKK9lfalkEE3Tbz1AFJdm2QLUzFxGEvIwUbfNBE1p'  ❌ (Don't include quotes)
```

---

### **3. SF_DOMAIN**
**In GitHub Secrets:**
```
login
```

**NOT:**
```
'login'  ❌ (Don't include quotes)
```

---

### **4. SF_PRIVATE_KEY**
**In GitHub Secrets:**
```
-----BEGIN RSA PRIVATE KEY-----
(paste entire content of your .pem file here)
(all lines including the header and footer)
-----END RSA PRIVATE KEY-----
```

**NOT:**
```
'-----BEGIN RSA PRIVATE KEY-----...'  ❌ (Don't include quotes)
```

**Important for SF_PRIVATE_KEY:**
- ✅ Include the header: `-----BEGIN RSA PRIVATE KEY-----`
- ✅ Include all lines in between
- ✅ Include the footer: `-----END RSA PRIVATE KEY-----`
- ✅ No quotes around it
- ✅ Keep all line breaks intact (paste as-is)

---

## 🔍 Why No Quotes?

**In Python files:**
```python
SF_USERNAME = 'afleming@innovativesol.com'  # Quotes are Python syntax
```

**In GitHub Secrets:**
```
afleming@innovativesol.com  # No quotes - just the value
```

The quotes (`'`) are part of Python syntax, not part of the actual credential value. GitHub Secrets stores the actual value, not Python code.

---

## ✅ Quick Reference

| Secret Name | Enter Value As | Example |
|------------|----------------|---------|
| `SF_USERNAME` | Email address (no quotes) | `afleming@innovativesol.com` |
| `SF_CONSUMER_KEY` | Consumer key (no quotes) | `3MVG98XJQQAccJQcGc5mps7vpffypZRfdV4YWfQxNgp0KKK9lfalkEE3Tbz1AFJdm2QLUzFxGEvIwUbfNBE1p` |
| `SF_DOMAIN` | Domain (no quotes) | `login` |
| `SF_PRIVATE_KEY` | Full .pem content (no quotes) | `-----BEGIN RSA PRIVATE KEY-----...` |

---

## 🎯 Summary

**Enter the value only - no quotes needed!** ✅

The quotes you see in `sf_config.py` are Python syntax, not part of the actual credential value.

