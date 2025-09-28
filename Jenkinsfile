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

# always start fresh this run
rm -f .console_url .public_ok .private_ok .why_public .why_private || true

PUB_URL="${APP_URL:-}"
PRIV_URL="${APP_URL_PRIVATE:-}"

echo "Public:  ${PUB_URL}"
echo "Private: ${PRIV_URL}"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

probe () {
  local url="$1" name="$2"
  [ -z "$url" ] && { echo "(${name}) empty URL, skipping"; return 1; }

  local host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}

  # TCP reachability
  if timeout 5 bash -lc ":</dev/tcp/$host/$port"; then
    echo "(${name}) TCP $host:$port reachable"
  else
    echo "(${name}) TCP $host:$port NOT reachable (timeout)"
    echo "tcp-timeout" > ".why_${name}"
    return 1
  fi

  # HTTP 200?
  code=$(curl -4 -sS -o /dev/null --connect-timeout 3 --max-time 5 \
             --noproxy '*' --proxy '' -w '%{http_code}' "$url" || echo "curl-error")
  echo "(${name}) HTTP code: $code"
  if [ "$code" = "200" ]; then
    : > ".${name}_ok"
    echo "$url" > ".${name}_url"
    return 0
  else
    echo "$code" > ".why_${name}"
    return 1
  fi
}

# probe public first, then private
probe "$PUB_URL"    "public"  || true
probe "$PRIV_URL"   "private" || true

# pick the URL to use:
if [ -f .public_ok ]; then
  cat .public_url > .console_url
elif [ -f .private_ok ]; then
  cat .private_url > .console_url
else
  echo "ERROR: neither public nor private console returned HTTP 200"
  echo "Public reason:  $(cat .why_public  2>/dev/null || echo 'n/a')"
  echo "Private reason: $(cat .why_private 2>/dev/null || echo 'n/a')"
  exit 1
fi

echo "Console URL selected: $(cat .console_url)"
echo "Public status:  $([ -f .public_ok ] && echo OK || echo FAIL:$(cat .why_public 2>/dev/null))"
echo "Private status: $([ -f .private_ok ] && echo OK || echo FAIL:$(cat .why_private 2>/dev/null))"
BASH
'''
  }
  post {
    success {
      script {
        if (fileExists('.console_url')) {
          def consoleUrl = readFile('.console_url').trim()
          echo "✅ Console URL in use: ${consoleUrl}"
        }
        echo "🛈 Private fallback (VPC-only): ${env.APP_URL_PRIVATE}"
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
      script {
        // Do NOT abort the pipeline automatically
        def qg = waitForQualityGate(abortPipeline: false)
        echo "Quality Gate status: ${qg.status} ${qg.description ?: ''}"
        if (qg.status != 'OK') {
          // Keep the build, but surface it clearly
          currentBuild.result = 'UNSTABLE'
        }
      }
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

  post {
    always {
      archiveArtifacts artifacts: 'logs/ansible-*.log, artifacts/**', allowEmptyArchive: true
    }
  }
}
