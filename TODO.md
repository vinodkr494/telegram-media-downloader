# 🚀 TG Media Downloader - v3.0 Roadmap Plan

> [!IMPORTANT]
> **We are currently focusing entirely on stabilizing and improving the robustness of existing features.** 
> If you have ideas or suggestions for new features, please join our [GitHub Discussions (Ideas)](https://github.com/vinodkr494/telegram-media-downloader/discussions/categories/ideas) instead of opening an issue. 

This document tracks the vision and high-level goals for the major **v3.0.0** release.

---

## ⚡ Core Engine & Performance
- [ ] **Segmented Multi-Connection**: Implement 8-16 parallel chunks per file for maximum throughput.
- [ ] **Auto-Cloud Synchronization**: Direct upload integration for **Google Drive, Dropbox, and OneDrive**.
- [ ] **External Engine Support**: Built-in support for of-loading tasks to **Aria2 or JDownloader 2**.
- [ ] **Anti-Flood Smart Pacing**: Intelligent traffic management to avoid Telegram's "Flood Wait" limits.

## 🎨 Visual & UI/UX Excellence
- [ ] **Media Preview Gallery View**: High-resolution grid-based thumbnail browser for easier selection.
- [ ] **Built-in Media Player**: Native player for previewing videos, music, and voice notes within the app.
- [ ] **Global Floating Mini-Widget**: Minimalist draggable overlay for tracking progress while the app is hidden.
- [ ] **Theme Personalization Engine**: Full custom `.qss` theme support and a primitive "Theme Creator" UI.

## 🔍 Advanced Content Discovery
- [ ] **Universal Global Search**: SQLite FTS5-powered keyword search across **ALL** previously fetched channel history.
- [ ] **AI Smart Renaming**: Lightweight local NLP to auto-rename files based on message context and captions.
- [ ] **Regex-Based Auto-Filters**: Create "Watcher" rules for automated file categorization and filtering.
- [ ] **Visual Duplicate Detection**: AI-powered similarity check to prune near-identical image downloads.

## 🤖 Automation & Scheduling
- [ ] **Download Scheduler**: Set custom "Active Windows" (e.g., 2 AM – 6 AM) for automated night downloads.
- [ ] **Auto-Join/Fetch/Leave Mode**: Provide a join link; app handles the rest and leaves the channel automatically.
- [ ] **Post-Download FFmpeg Pipeline**: Auto-convert `.ogg` to `.mp3` or `.mkv` to `.mp4` after completion.
- [ ] **Remote Web Dashboard**: Secure local web access to manage tasks from a mobile device or another PC.

## 🛡️ Management & Security
- [ ] **Dynamic Path Templating v2**: Advanced pathing, e.g., `/{category}/{year}/{month}/{msg_id}_{filename}.{ext}`.
- [ ] **Auto-Cleanup & Storage Rules**: Policies to maintain storage limits (e.g., "Keep only the last 100GB").
- [ ] **Mass Forwarding Engine**: Forward selected media batches to "Saved Messages" instead of downloading.
- [ ] **Python Plugin API**: Hook system for community-made filters and post-processing scripts.

---

## ✅ Progress Summary
- **Current Version**: 2.6.3
- **Next Milestone**: 2.7.0 (Cleanup & Refactor)
- **Primary Goal**: 3.0.0 (The Media Operating System)
