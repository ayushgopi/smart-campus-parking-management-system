document.addEventListener("DOMContentLoaded", () => {
    hideLoader();
    setupToasts();
    animateCounters();
    setupChart();
    setupParticles();
    setupParkingScene();
    staggerVisibleItems();
});

function hideLoader() {
    const loader = document.querySelector(".loading-screen");
    if (!loader) return;
    window.setTimeout(() => loader.classList.add("is-hidden"), 450);
}

function setupToasts() {
    document.querySelectorAll(".flash").forEach((toast) => {
        window.setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-10px)";
        }, 4200);
    });
}

function animateCounters() {
    document.querySelectorAll("[data-count]").forEach((node) => {
        const target = Number(node.dataset.count || 0);
        const duration = 900;
        const start = performance.now();
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            node.textContent = Math.round(target * easeOut(progress));
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    });
}

function easeOut(value) {
    return 1 - Math.pow(1 - value, 3);
}

function setupChart() {
    const chartCanvas = document.getElementById("occupancy-chart");
    const hero = document.querySelector(".dashboard-hero");
    if (!chartCanvas || !hero) return;

    const available = Number(hero.dataset.availableSlots || 0);
    const occupied = Number(hero.dataset.occupiedSlots || 0);
    const totalVehicles = Number(hero.dataset.totalVehicles || 0);
    const values = [available, occupied, totalVehicles];
    const labels = ["Available", "Occupied", "Vehicles"];
    const colors = ["#4ade80", "#fb7185", "#35d4ff"];

    if (!window.Chart) {
        drawFallbackChart(chartCanvas, values, labels, colors);
        return;
    }

    new Chart(chartCanvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: "rgba(255,255,255,0.12)",
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1200,
                easing: "easeOutQuart"
            },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        color: "#dbeafe",
                        font: { family: "Manrope", weight: "700" },
                        padding: 18
                    }
                }
            },
            cutout: "68%"
        }
    });
}

function drawFallbackChart(canvas, values, labels, colors) {
    const parent = canvas.parentElement;
    const width = Math.max(parent?.clientWidth || 360, 320);
    const height = 340;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = "100%";
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    const total = values.reduce((sum, value) => sum + value, 0) || 1;
    const cx = width / 2;
    const cy = 145;
    const radius = 92;
    const innerRadius = 58;
    let start = -Math.PI / 2;

    values.forEach((value, index) => {
        const angle = (value / total) * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, start, start + angle);
        ctx.arc(cx, cy, innerRadius, start + angle, start, true);
        ctx.closePath();
        ctx.fillStyle = colors[index];
        ctx.fill();
        start += angle;
    });

    ctx.fillStyle = "#f7fbff";
    ctx.font = "700 28px Manrope, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`${Math.round((values[1] / total) * 100)}%`, cx, cy + 4);
    ctx.fillStyle = "#9aa7bc";
    ctx.font = "700 12px Manrope, sans-serif";
    ctx.fillText("occupied", cx, cy + 26);

    labels.forEach((label, index) => {
        const x = 36 + index * Math.min(150, width / 3);
        const y = 292;
        ctx.fillStyle = colors[index];
        ctx.fillRect(x, y - 10, 12, 12);
        ctx.fillStyle = "#dbeafe";
        ctx.font = "700 13px Manrope, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(`${label}: ${values[index]}`, x + 20, y);
    });
}

function setupParticles() {
    const canvas = document.getElementById("particle-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const particles = Array.from({ length: 56 }, () => ({
        x: Math.random(),
        y: Math.random(),
        vx: (Math.random() - 0.5) * 0.00045,
        vy: (Math.random() - 0.5) * 0.00045,
        r: Math.random() * 1.8 + 0.7
    }));

    function resize() {
        canvas.width = window.innerWidth * window.devicePixelRatio;
        canvas.height = window.innerHeight * window.devicePixelRatio;
    }

    function frame() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "rgba(53, 212, 255, 0.52)";
        particles.forEach((particle) => {
            particle.x += particle.vx;
            particle.y += particle.vy;
            if (particle.x < 0 || particle.x > 1) particle.vx *= -1;
            if (particle.y < 0 || particle.y > 1) particle.vy *= -1;
            ctx.beginPath();
            ctx.arc(particle.x * canvas.width, particle.y * canvas.height, particle.r * window.devicePixelRatio, 0, Math.PI * 2);
            ctx.fill();
        });
        requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    frame();
}

function setupParkingScene() {
    const canvas = document.getElementById("parking-visual");
    if (!canvas || !window.THREE) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const group = new THREE.Group();
    scene.add(group);
    const mode = canvas.dataset.mode || "dashboard";

    const floor = new THREE.Mesh(
        new THREE.BoxGeometry(9, 0.08, 7),
        new THREE.MeshStandardMaterial({ color: 0x111827, metalness: 0.35, roughness: 0.42 })
    );
    floor.position.y = -0.08;
    group.add(floor);

    const slotMaterial = new THREE.MeshStandardMaterial({ color: 0x1f2937, metalness: 0.25, roughness: 0.35 });
    const glowGreen = new THREE.MeshStandardMaterial({ color: 0x4ade80, emissive: 0x103d22, metalness: 0.2, roughness: 0.25 });
    const glowRed = new THREE.MeshStandardMaterial({ color: 0xfb7185, emissive: 0x42111a, metalness: 0.2, roughness: 0.25 });

    for (let row = 0; row < 4; row += 1) {
        for (let col = 0; col < 6; col += 1) {
            const slot = new THREE.Mesh(new THREE.BoxGeometry(1.05, 0.08, 0.72), slotMaterial);
            slot.position.set((col - 2.5) * 1.35, 0.03, (row - 1.5) * 1.35);
            group.add(slot);

            if ((row + col) % 3 !== 0) {
                const car = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.28, 0.42), (row + col) % 2 === 0 ? glowGreen : glowRed);
                car.position.set(slot.position.x, 0.25, slot.position.z);
                group.add(car);
            }
        }
    }

    const heroCar = createHeroCar();
    heroCar.visible = mode === "landing";
    scene.add(heroCar);

    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x35d4ff, transparent: true, opacity: 0.55 });
    for (let i = -3; i <= 3; i += 1) {
        const points = [new THREE.Vector3(i * 1.35, 0.07, -3.4), new THREE.Vector3(i * 1.35, 0.07, 3.4)];
        group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), lineMaterial));
    }

    scene.add(new THREE.AmbientLight(0x9bdcff, 0.6));
    const key = new THREE.PointLight(0x35d4ff, 2.3, 24);
    key.position.set(2, 5, 4);
    scene.add(key);
    const fill = new THREE.PointLight(0x4ade80, 1.3, 18);
    fill.position.set(-4, 3, -3);
    scene.add(fill);

    camera.position.set(5, 6, 8);
    camera.lookAt(0, 0, 0);

    function resize() {
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(rect.width, 320);
        const height = Math.max(rect.height, 320);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }

    function animate() {
        group.rotation.y += mode === "landing" ? 0.0015 : 0.004;
        group.position.y = Math.sin(performance.now() * 0.0012) * 0.05;
        if (heroCar.visible) {
            const t = performance.now() * 0.001;
            heroCar.position.x = Math.sin(t * 0.9) * 3.4;
            heroCar.position.z = Math.cos(t * 0.9) * 1.35;
            heroCar.rotation.y = -t * 0.9 + Math.PI / 2;
            heroCar.position.y = 0.28 + Math.sin(t * 3) * 0.03;
        }
        renderer.render(scene, camera);
        requestAnimationFrame(animate);
    }

    resize();
    window.addEventListener("resize", resize);
    animate();
}

function createHeroCar() {
    const car = new THREE.Group();
    const bodyMaterial = new THREE.MeshStandardMaterial({
        color: 0x35d4ff,
        emissive: 0x082a35,
        metalness: 0.55,
        roughness: 0.24
    });
    const cabinMaterial = new THREE.MeshStandardMaterial({
        color: 0xdff9ff,
        emissive: 0x102a33,
        metalness: 0.2,
        roughness: 0.12,
        transparent: true,
        opacity: 0.82
    });
    const wheelMaterial = new THREE.MeshStandardMaterial({
        color: 0x05070c,
        metalness: 0.4,
        roughness: 0.35
    });
    const lightMaterial = new THREE.MeshStandardMaterial({
        color: 0x4ade80,
        emissive: 0x4ade80,
        emissiveIntensity: 1.8
    });

    const body = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.36, 0.72), bodyMaterial);
    body.position.y = 0.22;
    car.add(body);

    const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.32, 0.56), cabinMaterial);
    cabin.position.set(-0.08, 0.58, 0);
    car.add(cabin);

    const spoiler = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.08, 0.78), bodyMaterial);
    spoiler.position.set(-0.78, 0.54, 0);
    car.add(spoiler);

    const wheelGeometry = new THREE.CylinderGeometry(0.18, 0.18, 0.16, 24);
    [[0.48, 0.1, 0.43], [-0.48, 0.1, 0.43], [0.48, 0.1, -0.43], [-0.48, 0.1, -0.43]].forEach(([x, y, z]) => {
        const wheel = new THREE.Mesh(wheelGeometry, wheelMaterial);
        wheel.rotation.z = Math.PI / 2;
        wheel.position.set(x, y, z);
        car.add(wheel);
    });

    [[0.78, 0.28, 0.22], [0.78, 0.28, -0.22]].forEach(([x, y, z]) => {
        const light = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 16), lightMaterial);
        light.position.set(x, y, z);
        car.add(light);
    });

    car.scale.set(1.18, 1.18, 1.18);
    return car;
}

function staggerVisibleItems() {
    const items = document.querySelectorAll(".stat-card, .panel, .landing-strip article, .slot-card");
    items.forEach((item, index) => {
        item.style.animationDelay = `${index * 45}ms`;
        item.style.animationName = "pageIn";
        item.style.animationDuration = "0.55s";
        item.style.animationFillMode = "both";
    });
}
