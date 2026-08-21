# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-08-21

### Added
- Docker image (`Dockerfile`, multi-stage, `python:3.12-slim`) running behind gunicorn, with a `server` optional dependency group for the production WSGI server.
- GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that builds and pushes multi-arch (`linux/amd64` + `linux/arm64`) images to Docker Hub on `v*.*.*` tags, with semantic version tags (`1.2.0`/`1.2`/`1`/`latest`) and GitHub Actions layer caching.
- `README.md` **Docker** and **Deploy to Render** sections.
- This changelog.

## [0.1.0] - Initial extraction

### Added
- Project extracted from a `web/` folder inside a fork of [TheFlightWall_OSS](https://github.com/AxisNimble/TheFlightWall_OSS) into this standalone repository, renamed to OpenFlightWall.
