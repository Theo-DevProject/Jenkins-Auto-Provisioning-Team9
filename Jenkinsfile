pipeline {
  agent any
  options { timestamps() }

  environment {
    // ===== Ansible / App deploy =====
    INVENTORY   = "inventory.ini"
    PLAYBOOK    = "deploy-complete-system.yml"

    // App endpoints for smoke test
    APP_PUBLIC  = "http://3.223.42.1:8082"        // app-server Elastic IP
    APP_PRIVATE = "http://172.31.16.135:8082"     // app-server private

    // DB connection (use DB private IP)
    DB_HOST = "172.31.25.138"
    DB_USER = "devops"
    DB_PASS = "DevOpsPass456"
    DB_NAME = "syslogs"

    POINTS = "120"  // rows for snapshot

    // ===== SonarQube =====
    SONAR_HOST_URL    = "http://18.232.39.51:9000" // your SonarQube URL
    SONAR_PROJECT_KEY = "team9-syslogs"            // must match sonar-project.properties
    SONAR_USER_HOME   = "${WORKSPACE}/.sonar"      // scanner cache in workspace
    SONAR_WORK_DIR    = "${WORKSPACE}/.scannerwork"// scanner working dir
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
            if command -v apt-get >/dev/null 2>&1; then
              sudo apt-get update -y
              sudo apt-get install -y ansible python3-pip unzip
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
    // SonarQube (no Docker) - install locally in workspace
    // =======================
stage('Setup SonarScanner (no Docker)') {
  steps {
    sh '''
      set -e
      TOOLS="${WORKSPACE}/.tools"
      SC_HOME="${TOOLS}/sonar-scanner"
      mkdir -p "${SC_HOME}" "${SONAR_USER_HOME}" "${SONAR_WORK_DIR}"

      if [ ! -x "${SC_HOME}/latest/bin/sonar-scanner" ]; then
        echo "Installing SonarScanner in workspace..."
        TMP_ZIP="${TOOLS}/sonar-scanner.zip"
        rm -f "${TMP_ZIP}"

        VERSION="5.0.1.3006"
        URL="https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${VERSION}-linux.zip"

        if command -v curl >/dev/null 2>&1; then
          curl -sSfL "$URL" -o "${TMP_ZIP}"
        else
          wget -q "$URL" -O "${TMP_ZIP}"
        fi

        unzip -q "${TMP_ZIP}" -d "${SC_HOME}"
        rm -f "${TMP_ZIP}"

        REAL_DIR="$(find "${SC_HOME}" -maxdepth 1 -type d -name 'sonar-scanner-*' | head -n1)"
        [ -n "${REAL_DIR}" ] && mv "${REAL_DIR}" "${SC_HOME}/current"
        ln -snf "${SC_HOME}/current" "${SC_HOME}/latest" || true
      fi

      echo "export PATH=\\"${SC_HOME}/latest/bin:$PATH\\"" > .env.scanner
      . ./.env.scanner
      sonar-scanner -v
    '''
  }
}

    stage('SonarQube Scan') {
      steps {
        withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
          sh '''
            set -e
            . ./.env.scanner 2>/dev/null || true
            mkdir -p "${SONAR_USER_HOME}" "${SONAR_WORK_DIR}"
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
    }
  }
}
