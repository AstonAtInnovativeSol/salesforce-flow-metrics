# How to Add Workflow File on GitHub

## Step-by-Step Instructions

### Step 1: Go to Your Repository
1. Click on **"Code"** tab at the top of the page (not Settings)
2. You should now see your repository files

### Step 2: Navigate to .github/workflows/ Folder
1. Click on the **".github"** folder in the file list
2. Click on the **"workflows"** folder inside .github
3. If the folders don't exist, you'll need to create them first (see below)

### Step 3: Create the Workflow File
1. Click the **"Add file"** button (or **"Create new file"** button)
2. In the file name field, type: `run_scripts.yml`
3. Copy the contents from the file below
4. Scroll down and click **"Commit new file"**

---

## If .github/workflows/ Folders Don't Exist

If you don't see the `.github` folder:

1. Click **"Add file"** → **"Create new file"**
2. In the file name field, type: `.github/workflows/run_scripts.yml`
3. GitHub will automatically create the folders
4. Copy the file contents below
5. Click **"Commit new file"**

---

## Alternative: Use Command Line (Easier)

If you prefer, you can do it from your terminal:

```bash
cd "/Users/afleming/Desktop/Final Python Scripts"

# Copy workflow file to root .github folder
mkdir -p .github/workflows
cp "Live and migrated to GitHub/.github/workflows/run_scripts.yml" .github/workflows/run_scripts.yml

# Add and commit
git add .github/workflows/run_scripts.yml
git commit -m "Add GitHub Actions workflow"

# Push
git push origin main
```

---

## Workflow File Contents

Copy this entire content into the `run_scripts.yml` file:

