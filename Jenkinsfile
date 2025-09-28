pipeline {
  agent any

  options {
    timestamps()
    // Don’t overlap runs
    disableConcurrentBuilds(abortPrevious: true)
    // Keep history tidy
    buildDiscarder(logRotator(numToKeepStr: '20'))
    // Cap whole pipeline
    timeout(time: 30, unit: 'MINUTES')
  }

  parameters {
    // Default to Elastic IP so we always probe the public UI first
    string(
      name: 'APP_URL',
      defaultValue: 'http://3.223.42.1:8082',
      description: 'Public URL for SQL console (Elastic IP)'
    )
  }

  environment {
    INVENTORY = "inventory.ini"
    PLAYBOOK  = "deploy-complete-system.yml"

    // Private URL (for Jenkins → app over VPC)
    APP_URL_PRIVATE = "http://172.31.16.135:8082"

    // DB connection used by tools/snapshot.py
    DB_HOST = "172.31.25.138"
    DB_USER = "devops"
    DB_PASS = "DevOpsPass456"
    DB_NAME = "syslogs"

    POINTS = "120"
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Install Ansible deps (idempotent)') {
      steps {
        sh '''
          set -e
          if ! command -v ansible >/dev/null 2>&1; then
            sudo apt-get update -y
            sudo apt-get install -y ansible python3-pip
          fi
          ansible-galaxy collection install community.mysql community.general --force
        '''
      }
    }

    stage('Deploy with Ansible') {
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'devops-ssh',
                                           keyFileVariable: 'SSH_KEY',
                                           usernameVariable: 'SSH_USER')]) {
          sh '''
            set -e
            mkdir -p logs
            : > logs/ansible.log

            export ANSIBLE_HOST_KEY_CHECKING=false
            ansible --version

            ansible-playbook "${PLAYBOOK}" -i "${INVENTORY}" \
              -e ansible_ssh_private_key_file="$SSH_KEY" | tee -a logs/ansible.log

            cp logs/ansible.log "logs/ansible-${BUILD_NUMBER}.log"
          '''
        }
      }
    }

    stage('Smoke test: UI & API (public EIP preferred)') {
      steps {
        sh '''
/usr/bin/env bash <<'BASH'
set -euo pipefail

PUB_URL="${APP_URL:-}"          # Elastic IP from parameter
PRIV_URL="${APP_URL_PRIVATE}"   # VPC-only fallback
URLS="$PUB_URL $PRIV_URL"

echo "Probing (public first, then private fallback): $URLS"

# ensure no proxies interfere
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

rm -f .console_url

for url in $URLS; do
  [ -z "$url" ] && continue
  echo "Probing ${url} ..."
  host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}

  # quick TCP probe
  if timeout 5 bash -lc ":</dev/tcp/$host/$port"; then
    echo "TCP $host:$port is reachable"
  else
    echo "TCP $host:$port is NOT reachable (timeout)"
  fi

  # Try GET / (UI) up to 10 tries
  for i in $(seq 1 10); do
    code=$(curl -4 -sS -o /dev/null --connect-timeout 3 --max-time 5 \
               --noproxy '*' --proxy '' -w '%{http_code}' "$url/" || true)
    echo "UI Attempt $i/10 -> $url/ returned HTTP $code"
    [ "$code" = "200" ] && break
    sleep 2
  done

  # If UI is 200, test API with a safe default SELECT (must return JSON with rows/columns)
  # NOTE: the server accepts POST /api/query with {"sql": "..."} and requires LIMIT.
  # Use the same columns your dashboard expects.
  if curl -4 -fsS --connect-timeout 3 --max-time 5 "$url/" >/dev/null; then
    payload='{"sql":"SELECT memory_usage, cpu_usage, timestamp FROM stats ORDER BY timestamp DESC LIMIT 20;"}'
    echo "Hitting API: $url/api/query"
    resp=$(curl -4 -sS -X POST -H 'Content-Type: application/json' \
                 --connect-timeout 5 --max-time 8 \
                 --noproxy '*' --proxy '' \
                 -d "$payload" "$url/api/query" || true)
    echo "API sample response: $(echo "$resp" | cut -c1-200) ..."
    # very light validation: must have "rows" and "columns"
    echo "$resp" | grep -q '"rows"' && echo "$resp" | grep -q '"columns"'
    echo "$url" > .console_url
    exit 0
  fi
done

echo "ERROR: UI/API not reachable from Jenkins."
exit 1
BASH
'''
      }
      post {
        success {
          script {
            def consoleUrl = fileExists('.console_url') ? readFile('.console_url').trim() : params.APP_URL
            echo "✅ Console URL in use: ${consoleUrl}"
            echo "ℹ️  Private fallback (VPC-only): ${env.APP_URL_PRIVATE}"
          }
        }
      }
    }

    stage('Snapshot metrics (CSV + PNG)') {
      steps {
        sh '''
          set -e
          python3 -m venv .venv || true
          . .venv/bin/activate || true
          pip install --upgrade pip
          pip install pymysql matplotlib

          rm -rf artifacts && mkdir -p artifacts
          DB_HOST="${DB_HOST}" DB_USER="${DB_USER}" DB_PASS="${DB_PASS}" \
          DB_NAME="${DB_NAME}" POINTS="${POINTS}" \
          python tools/snapshot.py

          cp artifacts/stats_snapshot.csv "artifacts/stats_snapshot_${BUILD_NUMBER}.csv" || true
          cp artifacts/stats_last_hour.png "artifacts/stats_last_${BUILD_NUMBER}.png" || true
        '''
      }
    }

    /* ---------- SonarQube ---------- */

    stage('Setup SonarScanner (no Docker)') {
      steps {
        script {
          def scannerHome = tool 'sonar-scanner'
          sh """
            echo "Scanner home: ${scannerHome}"
            test -x "${scannerHome}/bin/sonar-scanner"
          """
        }
      }
    }

    stage('SonarQube Scan') {
      steps {
        withSonarQubeEnv('SonarQube') {
          script {
            def scannerHome = tool 'sonar-scanner'
            timeout(time: 25, unit: 'MINUTES') {
              sh """#!/usr/bin/env bash
                set -euo pipefail
                echo "Using SonarQube at: \${SONAR_HOST_URL}"
                echo "Scanner home: ${scannerHome}"

                "${scannerHome}/bin/sonar-scanner" \\
                  -Dsonar.projectKey=team9-syslogs \\
                  -Dsonar.projectName=team9-syslogs \\
                  -Dsonar.sources=roles/python_app,tools \\
                  -Dsonar.inclusions=**/*.py,**/*.yml,**/*.yaml,**/*.j2 \\
                  -Dsonar.exclusions=**/.venv/**,**/venv/**,**/.scannerwork/**,**/.git/**,**/__pycache__/**,**/*.egg-info/**,**/.history/**,.history/** \\
                  -Dsonar.secrets.enabled=false \\
                  -Dsonar.scm.disabled=true \\
                  -Dsonar.scanner.skipSystemTruststore=true
              """
            }
          }
        }
      }
    }

    stage('Quality Gate') {
      steps {
        timeout(time: 10, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
      post {
        always {
          script {
            def url = ''
            if (fileExists('.scannerwork/report-task.txt')) {
              def rt = readFile '.scannerwork/report-task.txt'
              url = (rt.readLines().find { it.startsWith('dashboardUrl=') } ?: '')
                    .replace('dashboardUrl=','')
            }
            echo url ? "SonarQube dashboard: ${url}" :
                       "Could not find dashboardUrl in report-task.txt"
          }
          archiveArtifacts artifacts: '.scannerwork/report-task.txt', allowEmptyArchive: true
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'logs/ansible-*.log, artifacts/**', allowEmptyArchive: true
    }
  }
}
