-- Exemplo 1: Contar issues por repositório
SELECT r.name, COUNT(*) AS total_issues
FROM issue i
JOIN repository r ON r.id = i.repository_id
GROUP BY r.name;

-- Exemplo 2: Contar commits por usuário
SELECT u.login, COUNT(*) AS total_commits
FROM commits c
JOIN user_info u ON u.id = c.user_id
GROUP BY u.login;

-- Exemplo 3: Repositório mais movimentado (issues + PRs + commits)
WITH activity AS (
    SELECT
        r.id,
        COUNT(DISTINCT i.id) +
        COUNT(DISTINCT pr.id) +
        COUNT(DISTINCT c.id) AS score
    FROM repository r
    LEFT JOIN issue i ON i.repository_id = r.id
    LEFT JOIN pull_requests pr ON pr.repository_id = r.id
    LEFT JOIN commits c ON c.pull_request_id = pr.id
    GROUP BY r.id
)
SELECT id FROM activity ORDER BY score DESC LIMIT 1;

-- Exemplo 4: Tasks (issues) por usuário em um repositório específico
SELECT
    u.login,
    COUNT(*) AS total_tasks
FROM issue i
JOIN user_info u ON u.id = i.created_by
WHERE i.repository_id = 1
GROUP BY u.login;
