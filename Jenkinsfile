pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds(abortPrevious: true)
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  // (Optional) keep param, but it will be overwritten by ips.json
  parameters {
    string(name: 'APP_URL', defaultValue: '', description: 'Will be set from ips.json if empty')
  }

  environment {
    INVENTORY = "inventory.ini"
    PLAYBOOK  = "deploy-complete-system.yml"
    POINTS    = "120"
    // These will be set after we load ips.json:
    // APP_URL
    // APP_URL_PRIVATE
    // DB_HOST
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

stage('Load IPs') {
  steps {
    script {
      // Read JSON once, accept either nested or flat structure
      def J = readJSON text: readFile('ips.json')
      def I = (J.ips instanceof Map) ? J.ips : J  // prefer nested .ips, fallback to flat

      // Build the env vars used later in the pipeline
      env.APP_URL         = "http://${I.app_public_ip}:${I.app_port}"
      env.APP_URL_PRIVATE = "http://${I.app_private_ip}:${I.app_port}"
      env.DB_HOST         = (I.mysql_private_ip ?: I.db_private_ip ?: '')
      env.SONAR_HOST_URL  = (I.sonarqube_host ?: env.SONAR_HOST_URL)

      echo "APP_URL: ${env.APP_URL}"
      echo "APP_URL_PRIVATE: ${env.APP_URL_PRIVATE}"
      echo "DB_HOST: ${env.DB_HOST}"
      if (env.SONAR_HOST_URL) echo "SONAR: ${env.SONAR_HOST_URL}"
    }
  }
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

            # Pass ips.json to Ansible (so roles can use it)
            ansible-playbook "${PLAYBOOK}" -i "${INVENTORY}" \
              -e ansible_ssh_private_key_file="$SSH_KEY" \
              -e "@ips.json" | tee -a logs/ansible.log

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
PUB_URL="${APP_URL:-}"
PRIV_URL="${APP_URL_PRIVATE:-}"
URLS="$PUB_URL $PRIV_URL"

echo "Probing (public then private): $URLS"
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy='*' NO_PROXY='*'

for url in $URLS; do
  [ -z "$url" ] && continue
  echo "Probing ${url} ..."
  host_port=${url#http://}; host=${host_port%:*}; port=${host_port##*:}
  if timeout 5 bash -lc ":</dev/tcp/$host/$port"; then echo "TCP $host:$port is reachable"; fi
  for i in $(seq 1 10); do
    code=$(curl -4 -sS -o /dev/null --connect-timeout 3 --max-time 5 --noproxy '*' --proxy '' -w '%{http_code}' "$url" || true)
    echo "Attempt $i/10 -> $url returned HTTP $code"
    if [ "$code" = "200" ]; then echo "$url" > .console_url; exit 0; fi
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
            def consoleUrl = fileExists('.console_url') ? readFile('.console_url').trim() : env.APP_URL
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
          DB_HOST="${DB_HOST}" DB_USER="devops" DB_PASS="DevOpsPass456" \
          DB_NAME="syslogs" POINTS="${POINTS}" \
          python tools/snapshot.py
          cp artifacts/stats_snapshot.csv "artifacts/stats_snapshot_${BUILD_NUMBER}.csv" || true
          cp artifacts/stats_last_hour.png "artifacts/stats_last_${BUILD_NUMBER}.png" || true
        '''
      }
    }

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
                "${scannerHome}/bin/sonar-scanner" \
                  -Dsonar.projectKey=team9-syslogs \
                  -Dsonar.projectName=team9-syslogs \
                  -Dsonar.sources=roles/python_app,tools \
                  -Dsonar.inclusions=**/*.py,**/*.yml,**/*.yaml,**/*.j2 \
                  -Dsonar.exclusions=**/.venv/**,**/venv/**,**/.scannerwork/**,**/.git/**,**/__pycache__/**,**/*.egg-info/**,**/.history/**,.history/** \
                  -Dsonar.secrets.enabled=false \
                  -Dsonar.scm.disabled=true \
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
            def qg = waitForQualityGate abortPipeline: false
            echo "Quality Gate status: ${qg.status}"
            // optionally: if (qg.status == 'ERROR') currentBuild.result = 'UNSTABLE'
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
  }

  post {
    always {
      archiveArtifacts artifacts: 'logs/ansible-*.log, artifacts/**', allowEmptyArchive: true
    }
  }
}
