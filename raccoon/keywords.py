"""Keyword and technology libraries for the firmographic profiler.

All comparisons are case-insensitive substring matches. Libraries are separated
from the profiler so they can be updated without touching scoring logic.
"""

SENSITIVITY_KEYWORDS = [
    "payroll", "health insurance", "benefits administration", "benefits management",
    "employee data", "employee documentation", "employee record",
    "PII", "personally identifiable",
    "HIPAA", "healthcare", "medical records", "patient data",
    "compliance", "regulatory compliance", "legal compliance",
    "tax filing", "tax preparation", "tax management",
    "financial services", "banking", "insurance", "credit card",
    "payment processing", "ACH", "wire transfer",
    "401k", "retirement plans", "retirement plan management",
    "workers compensation", "workers' compensation",
    "employment law", "employment law compliance",
    "background checks", "drug testing",
    "biometric data", "identity verification",
    "social security", "SSN",
    "data privacy", "data protection", "GDPR", "CCPA",
    "sensitive data", "confidential data",
    "HR data", "HR data security", "employee information",
    "benefits enrollment", "benefits administration platform",
    "global employment", "employer of record",
    "payroll processing", "payroll tax", "payroll services",
]

AI_STACK_TECHS = [
    "LangChain", "LangGraph", "LangSmith", "LangServe",
    "LlamaIndex", "CrewAI", "AutoGen", "AutoGPT",
    "Anthropic Claude", "Claude", "ChatGPT", "ChatGPT Enterprise",
    "GitHub Copilot", "Copilot",
    "Amazon Bedrock", "Amazon SageMaker", "SageMaker",
    "Google Vertex AI", "Vertex AI",
    "Azure OpenAI", "Azure AI",
    "MLflow", "Weights & Biases", "WandB",
    "Hugging Face", "HuggingFace",
    "Pinecone", "Chroma", "Weaviate", "Qdrant", "Milvus",
    "Airflow", "Prefect", "Dagster",
    "Temporal", "Temporal Cloud",
    "dbt", "dbt Cloud",
    "Snowflake", "Databricks",
    "Kafka", "Apache Kafka",
    "Fivetran", "Airbyte",
    "Synthesia", "Runway", "HeyGen",
    "Gong", "CallMiner",
]

SECURITY_TECHS = [
    "Okta", "Auth0", "Ping Identity", "SailPoint", "CyberArk",
    "OneTrust", "TrustArc",
    "KnowBe4", "Proofpoint", "Mimecast",
    "CrowdStrike", "SentinelOne", "Carbon Black",
    "Zscaler", "Netskope",
    "Cloudflare Bot Management", "Cloudflare WAF",
    "AWS GuardDuty", "AWS CloudTrail", "AWS Security Hub",
    "Wiz", "Orca Security", "Lacework",
    "Snyk", "Veracode", "Checkmarx",
    "Splunk", "Sumo Logic",
    "Palo Alto", "Fortinet", "Cisco Secure",
    "Varonis", "Imperva",
    "Osano", "Termly",
    "Upwind", "Lumia",
    "SSPM", "SaaS security",
]

INFRASTRUCTURE_TECHS = [
    "Amazon AWS", "AWS", "Microsoft Azure", "Azure",
    "Google Cloud", "GCP",
    "Snowflake", "Databricks", "BigQuery", "Redshift",
    "Kubernetes", "K8s", "Docker",
    "Terraform", "Pulumi", "CloudFormation",
    "Kafka", "Apache Kafka", "Amazon MSK",
    "Elasticsearch", "OpenSearch",
    "Redis", "Memcached",
    "Airflow", "Prefect", "Dagster",
    "Fivetran", "Airbyte", "Stitch",
    "dbt", "Dataform",
    "Temporal", "Temporal Cloud",
    "CircleCI", "GitHub Actions", "Jenkins",
    "Datadog", "New Relic", "Grafana",
    "Cloudflare", "Fastly", "Akamai",
    "Contentful", "Strapi", "Sanity",
    "GraphQL", "Apollo GraphQL",
    "Looker", "Tableau", "Metabase",
    "Salesforce", "NetSuite", "Workday",
]

HIGH_REGULATION_INDUSTRIES = [
    "financial services", "banking", "insurance",
    "healthcare", "hospital & health care", "medical practice",
    "pharmaceuticals", "biotechnology",
    "legal services", "law practice",
    "government administration", "defense & space", "military",
    "aviation & aerospace",
    "energy", "utilities", "oil & energy",
    "human resources", "staffing and recruiting",
    "accounting", "tax preparation",
]

REGULATORY_KEYWORDS = [
    "HIPAA", "SOX", "Sarbanes-Oxley",
    "GDPR", "CCPA", "CPRA",
    "PCI", "PCI DSS",
    "FedRAMP", "FISMA",
    "FINRA", "GLBA",
    "SOC 1", "SOC 2", "SOC 3",
    "ISO 27001", "NIST",
    "COBIT", "ITIL",
]
