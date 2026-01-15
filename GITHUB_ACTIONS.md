# GitHub Actions CI Guide

This document explains how to use GitHub Actions for automated testing in this project.

## What is GitHub Actions?

GitHub Actions automatically runs your tests whenever you push code or create a pull request. It's free for public repositories and runs on GitHub's servers - you don't need to set up anything locally.

## Accessing GitHub Actions

### 1. Go to the Actions Tab

1. Open your repository on GitHub: `https://github.com/YOUR_USERNAME/YOUR_REPO`
2. Click the **"Actions"** tab at the top of the page (between "Pull requests" and "Projects")

![Actions Tab Location](https://docs.github.com/assets/cb-15465/images/help/repository/actions-tab.png)

### 2. View Workflow Runs

You'll see a list of all workflow runs:
- **Green checkmark** ✅ = All tests passed
- **Red X** ❌ = Something failed
- **Yellow dot** 🟡 = Currently running
- **Gray dot** ⚫ = Queued or skipped

## When Do Tests Run?

Our workflow runs automatically when:

| Trigger | Condition |
|---------|-----------|
| **Push** | Any push to `master` or `main` branch that changes Python files |
| **Pull Request** | Any PR targeting `master` or `main` |
| **Manual** | You can trigger it manually anytime |

### Path Filtering

Tests only run when these files change:
- `docker/**/*.py` - Any Python file in docker/
- `docker/tests/**` - Any test file
- `.github/workflows/tests.yml` - The workflow itself

This saves CI minutes by skipping runs when you only change documentation or images.

## Running Tests Manually

### From GitHub Website

1. Go to **Actions** tab
2. Click **"Tests"** in the left sidebar
3. Click **"Run workflow"** button (top right)
4. Select the branch (usually `master`)
5. Click **"Run workflow"**

### From Command Line (using GitHub CLI)

```bash
# Install GitHub CLI if needed: https://cli.github.com/
gh workflow run tests.yml
```

## Understanding the Workflow

Our CI has **three jobs** that run:

```
┌─────────────────────────────────────────────────────────┐
│                    Tests Workflow                        │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐    ┌─────────┐    ┌──────────────┐
      │  test   │    │  lint   │    │  container   │
      │         │    │         │    │    build     │
      │ ~30 sec │    │ ~10 sec │    │   ~2 min     │
      └─────────┘    └─────────┘    └──────────────┘
           │               │               │
           └───────────────┴───────┬───────┘
                                   │
                            (must pass first)
```

### Job 1: test
- Installs Python 3.11 and dependencies
- Runs the standalone test runner (`tests/run_tests.py`)
- Runs pytest (`pytest tests/ -v`)

### Job 2: lint
- Checks Python syntax with `py_compile`
- Catches syntax errors before they break production

### Job 3: container-build
- **Only runs if test AND lint pass**
- Builds the Docker container to verify the Containerfile works
- Does NOT push to any registry (just validates)

## Reading Test Results

### Viewing a Workflow Run

1. Click on any workflow run in the Actions tab
2. You'll see the jobs and their status
3. Click on a job (e.g., "test") to see details

### Viewing Logs

1. Click on a job
2. Click on any step to expand its logs
3. Look for:
   - ✅ Green checkmarks = step passed
   - ❌ Red X = step failed (click to see error)

### Example: Finding a Failed Test

```
Run pytest tests/ -v
============================= test session starts ==============================
...
tests/test_core_logic.py::TestIsInThreshold::test_both_thresholds_both_pass PASSED
tests/test_core_logic.py::TestIsInThreshold::test_both_thresholds_ft_fails FAILED  ← Look here!
...
=================================== FAILURES ===================================
```

The failure message tells you exactly what went wrong.

## Adding a Status Badge to README

Add this line to your README.md to show build status:

```markdown
![Tests](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/tests.yml/badge.svg)
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual values.

The badge shows:
- ![passing](https://img.shields.io/badge/tests-passing-brightgreen) when tests pass
- ![failing](https://img.shields.io/badge/tests-failing-red) when tests fail

## Common Issues

### Tests Pass Locally But Fail in CI

**Different Python version:**
- CI uses Python 3.11
- Check your local version: `python3 --version`

**Missing dependencies:**
- Make sure all imports are in `requirements.txt`

**Path issues:**
- CI runs from the `docker/` directory
- Use relative paths in tests

### Workflow Not Running

**Check path filters:**
- Did you change a Python file? (not just docs/images)
- Is the file in `docker/` directory?

**Check branch:**
- Are you pushing to `master` or `main`?
- PRs must target `master` or `main`

### Container Build Fails

**Check Containerfile syntax:**
```bash
podman build -t test:latest .
```

**Check file permissions:**
- All Python files should be readable

## Notifications

### Email Notifications

By default, GitHub emails you when:
- A workflow you triggered fails
- A workflow on your PR fails

To change: **Settings** → **Notifications** → **Actions**

### Slack/Discord Integration

You can add notifications to Slack or Discord using GitHub Actions marketplace integrations.

## Cost and Limits

### Free Tier (Public Repos)
- **Unlimited** minutes for public repositories
- Our workflow uses ~3 minutes per run

### Private Repos
- 2,000 minutes/month free
- Our workflow uses ~3 minutes per run ≈ 600+ runs/month

## Quick Reference

| Task | How To |
|------|--------|
| View test results | Actions tab → Click workflow run |
| Run tests manually | Actions tab → Tests → Run workflow |
| See why tests failed | Click failed job → Expand failed step |
| Check if tests pass | Look for green checkmark ✅ |
| Add status badge | See "Adding a Status Badge" above |

## Running Tests Locally

Before pushing, run tests locally to catch issues early:

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker

# Quick standalone test (no dependencies needed)
python3 tests/run_tests.py

# Full pytest run (requires pytest installed)
pytest tests/ -v
```

## Workflow File Location

The workflow configuration is at:
```
docker/.github/workflows/tests.yml
```

You can edit this file to:
- Add more Python files to lint
- Change Python version
- Add new test commands
- Modify triggers
