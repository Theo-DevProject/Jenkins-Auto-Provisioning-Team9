pipeline {
  agent any
  options { timestamps() }

  environment {
    // ===== Ansible =====
    INVENTORY   = "inventory.ini"
    PLAYBOOK    = "deploy-complete-system.yml"

    // ===== App endpoints for smoke test =====
    APP_PUBLIC  = "http://3.223.42.1:8082"        // app-server Elastic IP
    APP_PRIVATE = "http://172.31.16.135:8082"     // app-server private

    // ===== DB connection (private IP) =====
    DB_HOST = "172.31.25.138"
    DB_USER = "devops"
    DB_PASS = "DevOpsPass456"
    DB_NAME = "syslogs"

    POINTS = "120"  // rows for snapshot

    // ===== SonarQube =====
    SONAR_HOST_URL    = "http://18.232.39.51:9000"  // your SonarQube URL
    SONAR_PROJECT_KEY = "team9-syslogs"             // must match sonar-project.properties
    // Sonar caches/work dir (kept inside workspace to avoid root perms)
    SONAR_USER_HOME   = "${WORKSPACE}/.sonar"
    SONAR_WORK_DIR    = "${WORKSPACE}/.scannerwork"
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Pre-flight: free space') {
      steps {
        sh '''
          set -e
          echo "Checking free space..."
          df -h
          # abort if less than ~1GB free on /
          FREE=$(df --output=avail -k / | tail -1)
          if [ "$FREE" -lt 1048576 ]; then
            echo "ERROR: Less than 1GB free on root filesystem."; exit 1
          fi
        '''
      }
    }

    stage('Install Ansible deps (idempotent)') {
      steps {
        sh '''
          set -e
          if ! command -v ansible >/dev/null 2>&1; then
            if command -v apt-get >/dev/null 2>&1; then
              sudo apt-get update -y
              sudo apt-get install -y ansible python3-pip
            else
              echo "Install Ansible on this agent first"; exit 1
            fi
          fi
          ansible-galaxy collection install community.mysql community.general --force
          mkdir -p logs
          : > logs/ansible.log
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
            export ANSIBLE_HOST_KEY_CHECKING=false
            ansible --version
            ansible-playbook "${PLAYBOOK}" -i "${INVENTORY}" \
              -e ansible_ssh_private_key_file="$SSH_KEY" | tee -a logs/ansible.log
            cp logs/ansible.log "logs/ansible-${BUILD_NUMBER}.log" || true
          '''
        }
      }
    }

    stage('Smoke test: SQL console up') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
URLS="${APP_PUBLIC} ${APP_PRIVATE}"
echo "Probing (public first): $URLS"

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

for url in $URLS; do
  echo "Probing ${url} ..."
  host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}
  tries=10
  if [[ $host =~ ^(10\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.|192\\.168\\.)$ ]]; then
    tries=5
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
    if [ "$code" = "200" ]; then
      echo "OK on $url"
      exit 0
    fi
    sleep 2
  done
done
echo "ERROR: SQL console not reachable from Jenkins (public nor private)."
exit 1
'''
      }
    }

    stage('Snapshot metrics (CSV + PNG)') {
      steps {
        sh '''
          set -e
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --upgrade pip
          pip install pymysql matplotlib

          rm -rf artifacts && mkdir -p artifacts
          DB_HOST="${DB_HOST}" DB_USER="${DB_USER}" DB_PASS="${DB_PASS}" \
          DB_NAME="${DB_NAME}" POINTS="${POINTS}" \
          .venv/bin/python tools/snapshot.py

          cp artifacts/stats_snapshot.csv "artifacts/stats_snapshot_${BUILD_NUMBER}.csv" || true
          cp artifacts/stats_last_hour.png "artifacts/stats_last_${BUILD_NUMBER}.png" || true
        '''
      }
    }

    // =======================
    // SonarQube (no Docker)
    // =======================
    stage('Setup SonarScanner (no Docker)') {
      steps {
        sh '''
          set -e
          if ! command -v sonar-scanner >/dev/null 2>&1; then
            echo "Installing SonarScanner CLI..."
            SC_ROOT="/opt/sonar-scanner"
            sudo mkdir -p "$SC_ROOT"
            cd "$SC_ROOT"
            # grab latest (adjust version if you want to pin)
            curl -sSLo scanner.zip https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli.zip
            sudo apt-get update -y && sudo apt-get install -y unzip
            sudo unzip -q scanner.zip
            sudo rm scanner.zip
            sudo ln -sf /opt/sonar-scanner/sonar-scanner-*/bin/sonar-scanner /usr/local/bin/sonar-scanner
          fi
          mkdir -p "${SONAR_USER_HOME}" "${SONAR_WORK_DIR}"
        '''
      }
    }

    stage('SonarQube Scan') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -e
            echo "Running SonarQube scan against ${SONAR_HOST_URL}..."
            export SONAR_HOST_URL="${SONAR_HOST_URL}"
            export SONAR_TOKEN="${SONAR_TOKEN}"
            export SONAR_USER_HOME="${SONAR_USER_HOME}"

            sonar-scanner \
              -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
              -Dsonar.working.directory="${SONAR_WORK_DIR}"
          '''
        }
      }
    }

    stage('SonarQube Report URL') {
      steps {
        echo "Open SonarQube: ${SONAR_HOST_URL}/projects?sort=-analysisDate"
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'logs/ansible-*.log, artifacts/**', allowEmptyArchive: true
      // Light cleanup of temp dirs (keep caches for speed if you prefer)
      sh '''
        rm -rf .venv || true
        # keep .sonar cache by default; uncomment to purge:
        # rm -rf "${SONAR_USER_HOME}" "${SONAR_WORK_DIR}" || true
      '''
    }
  }
}
