pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Docker') {
            steps {
                sh 'docker version'
                sh 'docker compose version'
            }
        }

        stage('Build stack') {
            steps {
                sh 'docker compose build'
            }
        }

        stage('Start Postgres') {
            steps {
                sh 'docker compose up -d postgres'
                sh '''
                    set -e
                    for i in $(seq 1 60); do
                      if docker compose exec -T postgres pg_isready -U postgres -d customer_prediction >/dev/null 2>&1; then
                        echo "Postgres is ready"
                        exit 0
                      fi
                      sleep 2
                    done
                    echo "Postgres did not become ready in time"
                    exit 1
                '''
            }
        }

        stage('Run migrations') {
            steps {
                sh 'docker compose run --rm backend python manage.py migrate --noinput'
            }
        }

        stage('Start backend') {
            steps {
                sh 'docker compose up -d backend'
            }
        }

        stage('Start frontend') {
            steps {
                sh 'docker compose up -d frontend'
            }
        }

        stage('Health checks') {
            steps {
                sh '''
                    set -e
                    echo "Waiting for backend..."
                    for i in $(seq 1 30); do
                      if docker compose exec -T backend sh -c "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8001/\")'" >/dev/null 2>&1; then
                        echo "Backend OK"
                        break
                      fi
                      if [ "$i" -eq 30 ]; then
                        echo "Backend health check failed"
                        exit 1
                      fi
                      sleep 2
                    done
                    echo "Waiting for frontend..."
                    for i in $(seq 1 30); do
                      if docker compose exec -T frontend sh -c "node -e \"fetch('http://127.0.0.1:3001/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\"" >/dev/null 2>&1; then
                        echo "Frontend OK"
                        break
                      fi
                      if [ "$i" -eq 30 ]; then
                        echo "Frontend health check failed"
                        exit 1
                      fi
                      sleep 2
                    done
                '''
            }
        }
    }

    post {
        always {
            sh 'docker compose down -v || true'
        }
    }
}
