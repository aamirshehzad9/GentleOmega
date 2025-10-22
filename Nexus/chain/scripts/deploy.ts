import { ethers } from "hardhat";

async function main() {
  const F = await ethers.getContractFactory("AgentRegistry");
  const c = await F.deploy();
  await c.waitForDeployment();
  console.log("AgentRegistry:", await c.getAddress());
}

main().catch((e) => { console.error(e); process.exit(1); });