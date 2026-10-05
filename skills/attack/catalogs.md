# catalogs.md

Collected from official OWASP sources, retrieved 2026-10-06. Re-collect through `web-researcher` when an edition changes; never edit ids or titles from memory.

## owasp-top10 — OWASP Top 10:2025

Source: https://top10.owasp.org/2025, retrieved 2026-10-06

- A01:2025 Broken Access Control — https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/
- A02:2025 Security Misconfiguration — https://top10.owasp.org/2025/A02_2025-Security_Misconfiguration/
- A03:2025 Software Supply Chain Failures — https://top10.owasp.org/2025/A03_2025-Software_Supply_Chain_Failures/
- A04:2025 Cryptographic Failures — https://top10.owasp.org/2025/A04_2025-Cryptographic_Failures/
- A05:2025 Injection — https://top10.owasp.org/2025/A05_2025-Injection/
- A06:2025 Insecure Design — https://top10.owasp.org/2025/A06_2025-Insecure_Design/
- A07:2025 Authentication Failures — https://top10.owasp.org/2025/A07_2025-Authentication_Failures/
- A08:2025 Software or Data Integrity Failures — https://top10.owasp.org/2025/A08_2025-Software_or_Data_Integrity_Failures/
- A09:2025 Security Logging and Alerting Failures — https://top10.owasp.org/2025/A09_2025-Security_Logging_and_Alerting_Failures/
- A10:2025 Mishandling of Exceptional Conditions — https://top10.owasp.org/2025/A10_2025-Mishandling_of_Exceptional_Conditions/

## owasp-llm — OWASP Top 10 for LLM Applications 2025

Source: https://genai.owasp.org/llm-top-10/, retrieved 2026-10-06

- LLM01:2025 Prompt Injection — https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- LLM02:2025 Sensitive Information Disclosure — https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/
- LLM03:2025 Supply Chain — https://genai.owasp.org/llmrisk/llm032025-supply-chain/
- LLM04:2025 Data and Model Poisoning — https://genai.owasp.org/llmrisk/llm042025-data-and-model-poisoning/
- LLM05:2025 Improper Output Handling — https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/
- LLM06:2025 Excessive Agency — https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- LLM07:2025 System Prompt Leakage — https://genai.owasp.org/llmrisk/llm072025-system-prompt-leakage/
- LLM08:2025 Vector and Embedding Weaknesses — https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/
- LLM09:2025 Misinformation — https://genai.owasp.org/llmrisk/llm092025-misinformation/
- LLM10:2025 Unbounded Consumption — https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/

## asvs — OWASP ASVS 5.0.0 (chapters)

Source: https://github.com/OWASP/ASVS/tree/v5.0.0, retrieved 2026-10-06. The project page labels 5.0.0 "Bleeding Edge"; the git tag v5.0.0 is the reference used here.

- V1 Encoding and Sanitization — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x10-V1-Encoding-and-Sanitization.md
- V2 Validation and Business Logic — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x11-V2-Validation-and-Business-Logic.md
- V3 Web Frontend Security — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x12-V3-Web-Frontend-Security.md
- V4 API and Web Service — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x13-V4-API-and-Web-Service.md
- V5 File Handling — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x14-V5-File-Handling.md
- V6 Authentication — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x15-V6-Authentication.md
- V7 Session Management — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x16-V7-Session-Management.md
- V8 Authorization — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x17-V8-Authorization.md
- V9 Self-contained Tokens — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x18-V9-Self-contained-Tokens.md
- V10 OAuth and OIDC — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x19-V10-OAuth-and-OIDC.md
- V11 Cryptography — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x20-V11-Cryptography.md
- V12 Secure Communication — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x21-V12-Secure-Communication.md
- V13 Configuration — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x22-V13-Configuration.md
- V14 Data Protection — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x23-V14-Data-Protection.md
- V15 Secure Coding and Architecture — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x24-V15-Secure-Coding-and-Architecture.md
- V16 Security Logging and Error Handling — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md
- V17 WebRTC — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x26-V17-WebRTC.md

## Mandatory minimum — checked under every catalog

Each maps to the catalogs above; the attack is attempted whatever catalog was chosen.

- XSS, including non-HTML sinks: push payloads, deep links and URL schemes, email HTML, markdown renderers — https://top10.owasp.org/2025/A05_2025-Injection/
- CSRF on every state-changing request authenticated by a cookie — https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x13-V4-API-and-Web-Service.md
- SQL injection, including blind (boolean and time-based) and second-order (stored, then concatenated later) — https://top10.owasp.org/2025/A05_2025-Injection/
- Slow queries an attacker controls: `LIKE '%input%'` on a large table, unbounded `LIMIT`/page size, deep `OFFSET`, regular expressions built from input (ReDoS), filters that compose into arbitrarily heavy queries — https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/ and https://github.com/OWASP/ASVS/blob/v5.0.0/5.0/en/0x11-V2-Validation-and-Business-Logic.md
- Prompt injection, direct (user input) and indirect (documents, web pages, tool output, stored data that reaches a prompt) — https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- Model output used as code, SQL, HTML, a URL or a shell command without the same handling as user input — https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/
