# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-01-18

### Added
- Initial release of WordPress Leads Extractor
- WordPress REST API integration via custom plugin
- MySQL database sync with automatic data cleaning
- Email validation and phone number standardization
- Quality scoring system (0-100) for leads
- Incremental sync capability for efficiency
- Duplicate detection and prevention
- Systemd service configuration for production deployment
- Comprehensive logging and error handling
- GitHub Actions CI/CD pipeline
- Docker support for containerized deployment
- Detailed documentation and deployment guide

### Features
- Extract leads from WordPress sweeprewards signups
- Support for multiple filtering options (date range, ID-based)
- Automatic data cleaning and validation
- Production-ready deployment scripts
- Monitoring and statistics tracking
- Export to JSON and CSV formats

### Security
- Environment-based configuration for credentials
- No hardcoded secrets in codebase
- Input validation and sanitization
- SQL injection prevention via parameterized queries

### Documentation
- Comprehensive README with installation instructions
- Deployment guide for production servers
- Contributing guidelines
- API documentation
- Database schema documentation

## [0.9.0] - 2024-01-15 (Beta)

### Added
- Beta version for testing
- Basic WordPress API integration
- Simple database storage
- Manual sync capability

### Changed
- Refactored API client for better error handling
- Improved database schema design

### Fixed
- Authentication issues with WordPress REST API
- Date filtering bugs

## [0.1.0] - 2024-01-10 (Alpha)

### Added
- Initial project structure
- Basic WordPress connection
- Proof of concept implementation

---

## Version History

- **1.0.0** - Production release with full feature set
- **0.9.0** - Beta release for testing
- **0.1.0** - Initial alpha version

## Upgrade Notes

### Upgrading from 0.9.0 to 1.0.0
1. Update WordPress plugin to v2 for new filtering capabilities
2. Run database migration: `mysql < migrations/v1.0.0.sql`
3. Update environment variables as per new `.env.example`
4. Restart systemd service after upgrade

[Unreleased]: https://github.com/rolling-riches/wordpress-leads-extractor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rolling-riches/wordpress-leads-extractor/releases/tag/v1.0.0
[0.9.0]: https://github.com/rolling-riches/wordpress-leads-extractor/releases/tag/v0.9.0
[0.1.0]: https://github.com/rolling-riches/wordpress-leads-extractor/releases/tag/v0.1.0