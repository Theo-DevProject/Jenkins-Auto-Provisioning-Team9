pipeline {
  agent any
  options { timestamps() }

  tools {
    jdk 'jdk17' // Manage Jenkins → Tools
  }

  environment {
    SCANNER_HOME = tool 'sonar-scanner'      // Manage Jenkins → Tools
    SONAR_SCANNER_OPTS = '-Xmx512m'
    INVENTORY = 'inventory.ini'
    PLAYBOOK  = 'deploy-complete-system.yml'
    APP_URL   = 'http://54.210.34.76:8082'   // public; OK if it times out but private succeeds
    DB_HOST = '172.31.25.138'
    DB_USER = 'devops'
    DB_PASS = 'DevOpsPass456'
    DB_NAME = 'syslogs'
    POINTS  = '120'
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

    stage('Smoke test: SQL console up') {
      steps {
        sh '''
/usr/bin/env bash <<'BASH'
set -Eeuo pipefail

URLS="${APP_URL} http://172.31.16.135:8082"
echo "Probing (public first): $URLS"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

for url in $URLS; do
  echo "Probing ${url} ..."
  host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}

  tries=3
  if [[ ! $host =~ ^(10\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.|192\\.168\\.)$ ]]; then
    tries=10
  fi

  if timeout 5 bash -lc ":</dev/tcp/$host/$port"; then
    echo "TCP $host:$port is reachable"
  else
    echo "TCP $host:$port is NOT reachable (timeout)"
  fi

  for i in $(seq 1 $tries); do
    code=$(curl -4 -sS -o /dev/null --connect-timeout 3 --max-time 5 \
               --noproxy '*' --proxy '' -w '%{http_code}' "$url" || true)
    echo "Attempt $i/$tries -> $url returned HTTP $code"
    if [[ "$code" == "200" ]]; then
      echo "OK on $url"
      exit 0
    fi
    sleep 2
  done
done

echo "ERROR: SQL console not reachable from Jenkins (public nor private)."
exit 1
BASH
'''
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
        sh '''
/usr/bin/env bash <<'BASH'
set -Eeuo pipefail
echo "SCANNER_HOME=${SCANNER_HOME}"
test -x "${SCANNER_HOME}/bin/sonar-scanner"
BASH
'''
      }
    }

    stage('SonarQube Scan') {
      steps {
        withSonarQubeEnv('SonarQube') {
          sh '''
#!/usr/bin/env bash
set -Eeuo pipefail

echo "SCANNER_HOME=${SCANNER_HOME}"
echo "Using SonarQube at: ${SONAR_HOST_URL}"

if [[ -f sonar-project.properties ]]; then
  "${SCANNER_HOME}/bin/sonar-scanner" -X
else
  "${SCANNER_HOME}/bin/sonar-scanner" -X \
    -Dsonar.projectKey=team9-syslogs \
    -Dsonar.projectName=team9-syslogs \
    -Dsonar.sources=.
fi

echo "---- report-task.txt ----"
cat .scannerwork/report-task.txt || true
'''
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
              def lines = readFile('.scannerwork/report-task.txt').readLines()
              url = (lines.find { it.startsWith('dashboardUrl=') } ?: '').replace('dashboardUrl=','')
            }
            echo url ? "SonarQube dashboard: ${url}" : 'Could not find dashboardUrl in report-task.txt'
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
