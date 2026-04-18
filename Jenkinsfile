pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
    }

    environment {
        COMPOSE_PROJECT_NAME = 'customer-recommendation-ci'
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
                    # Jenkins runs in Docker: localhost here is the Jenkins container, not the host where compose publishes ports.
                    echo "Waiting for backend (http://host.docker.internal:8001/)..."
                    for i in $(seq 1 30); do
                      if curl -fsS "http://host.docker.internal:8001/" >/dev/null 2>&1; then
                        echo "Backend OK"
                        break
                      fi
                      if [ "$i" -eq 30 ]; then
                        echo "Backend health check failed"
                        docker compose logs --tail 200 backend 2>&1 || true
                        exit 1
                      fi
                      sleep 2
                    done
                    echo "Waiting for frontend (http://host.docker.internal:3003/)..."
                    for i in $(seq 1 30); do
                      if curl -fsS "http://host.docker.internal:3003/" >/dev/null 2>&1; then
                        echo "Frontend OK"
                        break
                      fi
                      if [ "$i" -eq 30 ]; then
                        echo "Frontend health check failed"
                        docker compose logs --tail 200 frontend 2>&1 || true
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
