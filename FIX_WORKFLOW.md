# Fix Workflow File Push

## Issue

The workflow file `.github/workflows/run_scripts.yml` requires special permissions (`workflow` scope) to push.

## Solution Options

### Option 1: Add Workflow File via GitHub Web Interface (Easiest)

1. Go to: https://github.com/AstonAtInnovativeSol/salesforce-flow-metrics
2. Click **Create new file** or **Add file** → **Create new file**
3. Navigate to `.github/workflows/` folder
4. Name the file: `run_scripts.yml`
5. Copy the contents from `Live and migrated to GitHub/.github/workflows/run_scripts.yml`
6. Click **Commit new file**

### Option 2: Use Personal Access Token with Workflow Scope

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Create a new token with `workflow` scope
3. Use the token when pushing:
   ```bash
   git push https://YOUR_TOKEN@github.com/AstonAtInnovativeSol/salesforce-flow-metrics.git main
   ```

### Option 3: Push Workflow File Separately

After the main push succeeds, you can add the workflow file:

```bash
cd "/Users/afleming/Desktop/Final Python Scripts"

# Add workflow file
git add "Live and migrated to GitHub/.github/workflows/run_scripts.yml"

# Or create it in root
cp "Live and migrated to GitHub/.github/workflows/run_scripts.yml" .github/workflows/run_scripts.yml
git add .github/workflows/run_scripts.yml

# Commit and push
git commit -m "Add GitHub Actions workflow"
git push origin main
```

### Option 4: Use SSH Instead of HTTPS

If you have SSH keys set up:

```bash
# Change remote to SSH
git remote set-url origin git@github.com:AstonAtInnovativeSol/salesforce-flow-metrics.git

# Push
git push origin main
```

## Recommended: Option 1 (Web Interface)

The easiest way is to add the workflow file via GitHub's web interface. This avoids permission issues.

