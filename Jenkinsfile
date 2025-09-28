pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds(abortPrevious: true)
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  parameters {
    // Default to Elastic IP so public probe is preferred
    string(
      name: 'APP_URL',
      defaultValue: 'http://3.223.42.1:8082',
      description: 'Public URL for SQL console (Elastic IP)'
    )
  }

  environment {
    INVENTORY = "inventory.ini"
    PLAYBOOK  = "deploy-complete-system.yml"

    // Private URL (reachable from Jenkins over VPC)
    APP_URL_PRIVATE = "http://172.31.16.135:8082"

    // DB connection for the snapshot script
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
        withCredentials([
          sshUserPrivateKey(credentialsId: 'devops-ssh',
                            keyFileVariable: 'SSH_KEY',
                            usernameVariable: 'SSH_USER')
        ]) {
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

PUB_URL="${APP_URL:-}"                  # elastic IP by default (pipeline param)
PRIV_URL="${APP_URL_PRIVATE}"

# probe PUBLIC first, then PRIVATE as fallback
URLS="$PUB_URL $PRIV_URL"

echo "Probing (public then private): $URLS"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

for url in $URLS; do
  [ -z "$url" ] && continue
  echo "Probing ${url} ..."
  host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}

  if timeout 5 bash -lc ":</dev/tcp/$host/$port"; then
    echo "TCP $host:$port is reachable"
  else
    echo "TCP $host:$port is NOT reachable (timeout)"
  fi

  # up to 10 tries; fast-exit on HTTP 200
  for i in $(seq 1 10); do
    code=$(curl -4 -sS -o /dev/null --connect-timeout 3 --max-time 5 \
               --noproxy '*' --proxy '' -w '%{http_code}' "$url" || true)
    echo "Attempt $i/10 -> $url returned HTTP $code"
    if [ "$code" = "200" ]; then
      echo "OK on $url"
      echo "$url" > .console_url
      exit 0
    fi
    sleep 2
  done
done

echo "ERROR: SQL console not reachable from Jenkins."
exit 1
BASH
'''
      }
      post {
        success {
          script {
            def consoleUrl = fileExists('.console_url') ? readFile('.console_url').trim() : params.APP_URL
            echo "✅ Console URL in use: ${consoleUrl}"
            echo "🔒 Private fallback (VPC-only): ${env.APP_URL_PRIVATE}"
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
/* ----------unite test -------------*/
stage('Unit tests (pytest + coverage)') {
  steps {
    sh '''
      set -e
      python3 -m venv .venv || true
      . .venv/bin/activate
      pip install --upgrade pip
      pip install pytest pytest-cov

      # Create a minimal tests directory if it doesn’t exist
      mkdir -p tests

      # Example smoke test that at least imports your app
      cat > tests/test_imports.py <<'PY'
import importlib

def test_imports():
    # Import main console app to ensure it loads
    importlib.import_module("roles.python_app.files.sql_console")
PY

      # Run pytest with coverage
      pytest -q --maxfail=1 --disable-warnings \
        --cov=roles/python_app/files --cov-report=xml:coverage.xml
    '''
    archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
  }
}
/* ---------------sonarqube scane ---------*/
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

            "${scannerHome}/bin/sonar-scanner" \
              -Dsonar.projectKey=team9-syslogs \
              -Dsonar.projectName=team9-syslogs \
              -Dsonar.sources=roles/python_app,tools \
              -Dsonar.inclusions=**/*.py,**/*.yml,**/*.yaml,**/*.j2 \
              -Dsonar.exclusions=**/.venv/**,**/venv/**,**/.scannerwork/**,**/.git/**,**/__pycache__/**,**/*.egg-info/**,**/.history/**,.history/** \
              -Dsonar.python.coverage.reportPaths=coverage.xml \
              -Dsonar.secrets.enabled=false \
              -Dsonar.scm.disabled=true \
              -Dsonar.scanner.skipSystemTruststore=true
          """
        }
      }
    }
  }
}
/* -------quality gate check --------*/
    stage('Quality Gate') {
      steps {
        timeout(time: 10, unit: 'MINUTES') {
          script {
            // Don’t abort the pipeline; mark UNSTABLE if gate not OK
            def qg = waitForQualityGate(abortPipeline: false)
            echo "Quality Gate status: ${qg.status} ${qg.description ?: ''}"
            if (qg.status != 'OK') {
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
/* ----end stages -----*/
  } // stages

  post {
    always {
      archiveArtifacts artifacts: 'logs/ansible-*.log, artifacts/**', allowEmptyArchive: true
    }
  }
}
